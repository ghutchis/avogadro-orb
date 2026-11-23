#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").
#  https://github.com/ghutchis/avogadro-orb/

"""Entry point for the avogadro-orb plugin.

Avogadro calls this as:
    avogadro-orb <identifier> --protocol binary-v1 [--lang <locale>] [--debug]

with the molecule bootstrap JSON on stdin as one compact line, followed by
binary coordinate frames for as long as the model stays loaded.
"""

import argparse
import os

# Protect the binary protocol stream at the file-descriptor level before any
# heavy library is imported: ML dependencies print to stdout (including from
# C/C++), and Avogadro never resyncs after a stray byte. Frames go to a private
# duplicate of the original stdout; fd 1 itself now points at stderr.
PROTO_OUT = None


def _protect_stdout():
    global PROTO_OUT
    if PROTO_OUT is None:
        PROTO_OUT = os.fdopen(os.dup(1), "wb")
        os.dup2(2, 1)


def setup():
    """Download the weights for every exposed model.

    Avogadro runs this once after installing the plugin, so the first energy
    evaluation does not stall on a download.
    """
    from .orb_v3 import setup as setup_orb_v3
    from .orbmol_v2 import setup as setup_orbmol_v2

    print("Preparing OrbMol-v2 (downloading weights if needed)...", flush=True)
    setup_orbmol_v2()
    print("Preparing Orb-v3 (downloading weights if needed)...", flush=True)
    setup_orb_v3()
    print("avogadro-orb setup complete.", flush=True)


def main():
    parser = argparse.ArgumentParser("avogadro-orb")
    # Avogadro always passes the feature identifier as the first argument.
    parser.add_argument("feature")
    # Every plugin must accept these without crashing, even if it ignores them.
    parser.add_argument("--lang", nargs="?", default="en")
    parser.add_argument("--debug", action="store_true")
    # Sent for any energy model declaring protocol = "binary-v1".
    parser.add_argument("--protocol", nargs="?", default="binary-v1")
    args = parser.parse_args()
    _protect_stdout()

    # Handlers are imported inside each branch so that a slow dependency is
    # only loaded by the feature that actually needs it.
    match args.feature:
        case "OrbMol-v2":
            from .orbmol_v2 import run
            run()
        case "Orb-v3":
            from .orb_v3 import run
            run()
