"""Legacy logging utilities bridging to shared implementation."""
import sys
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists() and str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

try:
    from tiger_guides.logging import setup_logger  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from lib.utils.logger import setup_logger  # fallback

__all__ = ["setup_logger"]
