"""Helpers for locating TIGER model artefacts."""
from pathlib import Path
from typing import Dict


def resolve_model_paths(config: Dict[str, str], root: Path) -> Dict[str, Path]:
    model_dir = root / config["model_path"]
    calibration = root / config["calibration_params"]
    scoring = root / config["scoring_params"]

    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    if not calibration.exists():
        raise FileNotFoundError(f"Calibration parameters not found: {calibration}")
    if not scoring.exists():
        raise FileNotFoundError(f"Scoring parameters not found: {scoring}")

    return {
        "model_path": model_dir,
        "calibration_params": calibration,
        "scoring_params": scoring,
    }
