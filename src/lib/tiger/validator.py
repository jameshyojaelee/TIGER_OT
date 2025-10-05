"""Compatibility wrapper for shared TIGER validators."""
import sys
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[3] / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists() and str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from tiger_guides.tiger.validator import validate_tiger_output, check_guide_quality

__all__ = ["validate_tiger_output", "check_guide_quality"]
