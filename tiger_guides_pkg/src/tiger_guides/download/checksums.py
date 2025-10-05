"""Checksum utilities for tiger_guides downloads."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

from ..constants import SPECIES_CATALOG


def get_expected_checksums() -> Dict[str, str]:
    checksums: Dict[str, str] = {}
    for species, meta in SPECIES_CATALOG.items():
        checksum = meta.get("reference_md5")
        if checksum:
            checksums[meta["reference_filename"]] = checksum
    return checksums


def md5sum(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(path: Path, expected: str) -> bool:
    return md5sum(path) == expected.lower()
