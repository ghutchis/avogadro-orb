#  This source file is part of the Avogadro project.
#  This source code is released under the 3-Clause BSD License, (see "LICENSE").

"""Orb-v3 conservative OMat24 model: periodic, neutral only."""

from ._orb_server import run_orb_server, setup as _setup


def run():
    run_orb_server("Orb-v3")


def setup():
    _setup("Orb-v3")
