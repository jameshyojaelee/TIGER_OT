"""Helpers for locating TIGER model artefacts."""
from importlib import resources
from pathlib import Path
from typing import Dict


def _resolve_with_fallback(relative_path: str, root: Path) -> Path:
    candidate = root / relative_path
    if candidate.exists():
        return candidate

    package_root = resources.files("tiger_guides")
    fallback = package_root / relative_path
    if fallback.exists():
        return Path(str(fallback))

    # Some packages prefix resources/ for clarity; handle that gracefully.
    # e.g. config points to "resources/models/..." but pkg contains
    # "resources/resources/models/..." or vice versa.
    alt = package_root / "resources" / relative_path
    if alt.exists():
        return Path(str(alt))

    raise FileNotFoundError(f"Model asset not found: {relative_path} (searched {candidate} and package resources)")


def resolve_model_paths(config: Dict[str, str], root: Path) -> Dict[str, Path]:
    model_dir = _resolve_with_fallback(config["model_path"], root)
    calibration = _resolve_with_fallback(config["calibration_params"], root)
    scoring = _resolve_with_fallback(config["scoring_params"], root)

    return {
        "model_path": model_dir,
        "calibration_params": calibration,
        "scoring_params": scoring,
    }
