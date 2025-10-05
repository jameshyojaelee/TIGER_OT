"""Configuration utilities for the portable TIGER workflow."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .constants import DATA_DIR, SPECIES_CATALOG, DEFAULT_ENS_URL, DEFAULT_RATE_LIMIT


@dataclass(frozen=True)
class SpeciesOption:
    name: str

    def __post_init__(self):
        normalized = self.name.lower()
        if normalized not in SPECIES_CATALOG:
            raise ValueError(
                f"Unsupported species '{self.name}'. Available options: {', '.join(SPECIES_CATALOG)}"
            )
        object.__setattr__(self, "name", normalized)

    @property
    def metadata(self) -> Dict[str, Any]:
        return SPECIES_CATALOG[self.name]

    @property
    def ensembl_name(self) -> str:
        return self.metadata["ensembl_name"]

    @property
    def reference_filename(self) -> str:
        return self.metadata["reference_filename"]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def default_config_path() -> Path:
    return DATA_DIR / "defaults" / "config.yaml"


def load_config(config_path: Optional[Path], species: SpeciesOption) -> Dict[str, Any]:
    """Load workflow configuration, injecting species-specific paths."""
    if config_path is None:
        config_path = default_config_path()
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = load_yaml(config_path)

    # Normalise config
    config = copy.deepcopy(config)
    config.setdefault("ensembl", {})
    config["ensembl"].setdefault("rest_url", DEFAULT_ENS_URL)
    config["ensembl"].setdefault("rate_limit_delay", DEFAULT_RATE_LIMIT)

    config["species"] = species.ensembl_name
    config.setdefault("species_options", {})
    config["species_options"][species.name] = species.metadata

    # Ensure off-target section exists
    offtarget = config.setdefault("offtarget", {})
    offtarget.setdefault("max_mismatches", 5)
    offtarget.setdefault("binary_path", "bin/offtarget_search")
    offtarget.setdefault("reference_dir", "references")
    offtarget.setdefault("chunk_size", 1200)

    # reference path will be resolved by download.references when necessary
    offtarget.setdefault("reference_transcriptome", species.metadata["reference_filename"])

    # Provide defaults for compute + filtering if missing
    config.setdefault("filtering", {})
    config.setdefault("compute", {})
    config.setdefault("output", {})

    return config


def config_to_json(config: Dict[str, Any]) -> str:
    return json.dumps(config, indent=2, sort_keys=True)
