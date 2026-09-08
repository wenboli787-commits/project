"""Simulator-agnostic evaluation toolkit for humanoid motion retargeting.

The command-line entry point can be run either as a script or as
``python -m evaluate.evaluate_retargeting`` from the GMR directory.
"""

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from canonical_motion import CanonicalMotion

__all__ = ["CanonicalMotion"]
