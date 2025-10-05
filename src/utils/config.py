"""Legacy configuration utilities bridging to shared implementation."""
import sys
from pathlib import Path
from typing import Any, Dict

PACKAGE_SRC = Path(__file__).resolve().parents[1] / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists() and str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from lib.utils.config import load_config as legacy_load_config
from lib.utils.config import save_config as legacy_save_config
from lib.utils.config import merge_configs as legacy_merge_configs


def load_config(config_path):
    return legacy_load_config(config_path)


def save_config(config: Dict[str, Any], output_path):
    legacy_save_config(config, output_path)


def merge_configs(base_config, override_config):
    return legacy_merge_configs(base_config, override_config)
