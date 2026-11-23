#  This source file is part of the Avogadro project.
#  This source code is released under the 3-Clause BSD License, (see "LICENSE").

"""Shared EnergyServer loop and calculator factory for the Orb models."""

import contextlib
import json
import os
import sys

import numpy as np

# eV -> kJ/mol
_EV_TO_KJ_MOL = 96.4853321

# "charge_spin" marks models that must be told the total charge and spin
# multiplicity (OrbMol); Orb-v3 OMat is neutral only.
MODELS = {
    "OrbMol-v2": {"function": "orbmol_v2", "charge_spin": True},
    "Orb-v3": {
        "function": "orb_v3_conservative_inf_omat",
        "charge_spin": False,
    },
}


@contextlib.contextmanager
def quiet_stdout():
    """Send everything written to file descriptor 1 to stderr.

    Dependencies (Warp, download progress bars) print to stdout, which is the
    binary protocol channel. Redirecting the descriptor also catches C-level
    writes.
    """
    sys.stdout.flush()
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def proto_out():
    """The private protocol stream set up by avogadro_orb.main()."""
    from . import PROTO_OUT

    return PROTO_OUT if PROTO_OUT is not None else sys.stdout.buffer


def device_name():
    import torch

    # Never MPS: no float64.
    return "cuda" if torch.cuda.is_available() else "cpu"


def make_calculator(identifier):
    """Build the ASE calculator for an exposed model identifier."""
    with quiet_stdout():
        from orb_models.forcefield import pretrained
        from orb_models.forcefield.inference.calculator import ORBCalculator

        device = device_name()
        loader = getattr(pretrained, MODELS[identifier]["function"])
        # float64 gives gradients accurate enough for optimization;
        # compile=False avoids a long torch.compile JIT at every startup.
        model, adapter = loader(
            device=device, precision="float64", compile=False
        )
        return ORBCalculator(model, atoms_adapter=adapter, device=device)


def setup(identifier):
    """Download the weights for a model and run one small calculation."""
    from ase.build import molecule

    atoms = molecule("H2O")
    if MODELS[identifier]["charge_spin"]:
        atoms.info["charge"] = 0
        atoms.info["spin"] = 1
    atoms.calc = make_calculator(identifier)
    with quiet_stdout():
        atoms.get_potential_energy()
        atoms.get_forces()


def run_orb_server(identifier):
    from ase import Atoms
    from ase.cell import Cell

    from avogadro.energy import EnergyServer

    # Read the bootstrap line from the binary buffer, never the text wrapper.
    bootstrap = json.loads(sys.stdin.buffer.readline())
    mol_cjson = bootstrap["cjson"]

    atom_numbers = np.array(mol_cjson["atoms"]["elements"]["number"])
    coordinates = np.array(
        mol_cjson["atoms"]["coords"]["3d"], dtype=float
    ).reshape(-1, 3)
    # num_atoms must be the full count C++ uses in every binary frame.
    num_atoms = len(atom_numbers)

    # Avogadro includes periodic image atoms at fractional coordinate ~1.0;
    # drop them for the calculator and put zero gradients back for them.
    keep = np.ones(num_atoms, dtype=bool)
    if "unitCell" in mol_cjson:
        frac_list = mol_cjson["atoms"]["coords"].get("3dFractional", [])
        if frac_list:
            frac = np.array(frac_list, dtype=float).reshape(-1, 3)
            keep = ~np.any(np.abs(frac - 1.0) < 1e-4, axis=1)
        lattice = np.array(
            mol_cjson["unitCell"]["cellVectors"], dtype=float
        ).reshape(3, 3)
        atoms = Atoms(
            atom_numbers[keep], coordinates[keep], cell=Cell(lattice), pbc=True
        )
    else:
        atoms = Atoms(atom_numbers, coordinates, pbc=False)

    if MODELS[identifier]["charge_spin"]:
        # Avogadro's "spin" is the total spin multiplicity (2S+1), which is
        # what OrbMol expects in atoms.info["spin"].
        atoms.info["charge"] = int(round(float(bootstrap.get("charge", 0))))
        atoms.info["spin"] = max(1, int(round(float(bootstrap.get("spin", 1)))))

    atoms.calc = make_calculator(identifier)

    def gradient(forces):
        grad_full = np.zeros((num_atoms, 3), dtype=np.float64)
        grad_full[keep] = forces * -_EV_TO_KJ_MOL
        return grad_full

    with EnergyServer(sys.stdin.buffer, proto_out(), num_atoms) as server:
        for request in server.requests():
            try:
                atoms.set_positions(request.coords[keep])
                if request.wants_energy_and_gradient:
                    energy = float(atoms.get_potential_energy())
                    forces = atoms.get_forces()
                elif request.wants_gradient:
                    forces = atoms.get_forces()
                else:
                    energy = float(atoms.get_potential_energy())
                if request.wants_energy_and_gradient:
                    request.send_energy_and_gradient(
                        energy * _EV_TO_KJ_MOL, gradient(forces)
                    )
                elif request.wants_gradient:
                    request.send_gradient(gradient(forces))
                else:
                    request.send_energy(energy * _EV_TO_KJ_MOL)
            except Exception as error:  # noqa: BLE001
                request.send_error(str(error))
