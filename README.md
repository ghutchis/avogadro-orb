# avogadro-orb

Energy and gradient models from Orbital Materials' Orb family, via the
[orb-models](https://github.com/orbital-materials/orb-models) package.
Conservative (energy-derived force) models only, run in float64 on CUDA if
available, otherwise on CPU (never MPS).

## Models

| Name | Checkpoint | Systems | Elements |
| --- | --- | --- | --- |
| OrbMol-v2 | `orbmol-v2-teqabfhg-20260523` | molecules and periodic; charged and open-shell | 1-86, 88-99 |
| Orb-v3 (OMat24) | `orb-v3-conservative-inf-omat-20250404` | periodic materials; neutral, closed shell only | 1-88 |

- **OrbMol-v2**: trained on OMol25 and OPoly26 (wB97M-V/def2-TZVPD) with
  learnable electrostatics (Coulomb sum for molecules, PME for periodic cells).
  Avogadro's total charge and spin multiplicity are passed to the model.
- **Orb-v3**: trained on OMat24 (PBE/PBE+U). It has no charge or spin input, so
  Avogadro hides it for ions and radicals.

Element lists come from the model code, not the papers: the reference-energy
tables in the loaded checkpoints are fitted for exactly those atomic numbers
(OrbMol-v2 has no entry for Fr and none above Es; Orb-v3 shares one constant
for every element above Ra, i.e. untrained). The network embeddings themselves
accept up to Z = 117, so heavier elements run but are meaningless.

## Citations

- Rhodes et al., "Orb-v3: atomistic simulation at scale", arXiv:2504.06231.
- Orbital Materials, OrbMol / OrbMol-v2 (see the orb-models README and
  MODELS.md) and the OMol25 and OMat24 datasets.

## Licenses

The orb-models code and the released model weights are Apache-2.0. This plugin
is BSD-3-Clause. (The OMol25 / OMat24 / OPoly26 datasets carry their own
licenses; see their publications.)

## Platforms

Locks for osx-arm64 and linux-64. Only osx-arm64 has been tested; linux-64
(CPU or CUDA) is untested. Upstream supports macOS and Linux; Windows is "not
guaranteed", so it is not listed. Python is pinned to 3.12 because orb-models
requires `dm-tree==0.1.8`, which has no wheels for newer Pythons.

The first Warp kernel compilation happens during `pixi run setup`, which also
downloads both checkpoints (about 100 MB each). Cold start of the model
process afterward is roughly 10 s on an Apple M-series CPU.

## Development

```bash
pixi install
pixi run setup   # downloads both checkpoints and compiles Warp kernels
pixi run test    # protocol tests against both models (about 4 minutes)
```

Python is 3.12 only: orb-models requires `dm-tree==0.1.8`, which has no
wheels for 3.13 or newer and does not build from source there.

Orb-v3 is a materials model trained on OMat24 (periodic crystals). It is not
meant for isolated molecules, although Avogadro offers it for any neutral
system; use OrbMol-v2 for molecules.

Files in `src/avogadro_orb/`:

- `__init__.py`: the entry point (`main`, `setup`). `main` first moves the
  protocol stream to a private duplicate of stdout and points fd 1 at stderr,
  so library output cannot corrupt the binary frames.
- `_orb_server.py`: the model table, calculator construction (float64, CUDA if
  available else CPU), and the `EnergyServer` loop with periodic image-atom
  filtering and kJ/mol, gradient (not force) conversion.
- `orbmol_v2.py` and `orb_v3.py`: thin per-model `run()` and `setup()`.

Avogadro starts one process per model, as
`pixi run avogadro-orb OrbMol-v2 --protocol binary-v1`, sends one bootstrap
JSON line (including total `charge` and spin multiplicity `spin`), then
exchanges binary frames until it closes stdin.

`pixi run test` drives the real protocol in a subprocess for each model. It
checks gradients against finite differences, periodic image-atom handling,
that stdout carries only protocol frames, and that the first bytes are `AVB1`.

To add a model, add an entry to `MODELS` in `_orb_server.py`, a
`[[tool.avogadro.energy-models]]` block in `pyproject.toml` (with
`support.*` keys that match what the model actually handles), a module like
`orb_v3.py`, a matching `case` in `__init__.py`, and download it in `setup()`.

## Installing

In Avogadro: **Extensions → Plugin Manager → Install from directory**, and
choose this folder.

## Suggestions

Please file suggestions and bugs at
<https://github.com/ghutchis/avogadro-orb/issues>.
