#  This source file is part of the Avogadro project.
#  This source code is released under the 3-Clause BSD License, (see "LICENSE").

"""OrbMol-v2: molecular and periodic, charge and spin aware."""

from ._orb_server import run_orb_server, setup as _setup


def run():
    run_orb_server("OrbMol-v2")


def setup():
    _setup("OrbMol-v2")
