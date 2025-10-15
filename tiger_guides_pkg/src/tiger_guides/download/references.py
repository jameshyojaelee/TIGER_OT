"""Reference transcriptome management."""
from __future__ import annotations

import gzip
import os
import shutil
from pathlib import Path
from typing import Optional

import requests

from ..config import SpeciesOption
from ..constants import SPECIES_CATALOG, SMOKE_DIR
from .checksums import get_expected_checksums, verify_checksum

CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _skip_checksum(skip_flag: bool) -> bool:
    env_value = os.environ.get("TIGER_SKIP_REFERENCE_CHECKSUM", "").strip().lower()
    env_skip = env_value in {"1", "true", "yes", "on"}
    return skip_flag or env_skip


def ensure_reference(
    species: SpeciesOption,
    cache_dir: Path,
    prefer_smoke: bool = True,
    skip_checksum: bool = False,
) -> Path:
    """Ensure the transcriptome for ``species`` exists under ``cache_dir``.

    Returns the path to the transcriptome FASTA.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = species.reference_filename
    destination = cache_dir / filename

    skip_checksum = _skip_checksum(skip_checksum)
    checksums = get_expected_checksums()

    if destination.exists():
        if not skip_checksum:
            expected = checksums.get(filename)
            if expected and not verify_checksum(destination, expected):
                destination.unlink()
            else:
                return destination
        else:
            return destination

    # Special-case smoke dataset for mouse
    if prefer_smoke and species.name == "mouse":
        smoke_reference = SMOKE_DIR / "gencode.vM37.transcripts.uc.joined"
        if smoke_reference.exists():
            shutil.copy2(smoke_reference, destination)
            return destination

    url: Optional[str] = SPECIES_CATALOG[species.name].get("reference_url")
    if not url:
        raise FileNotFoundError(
            f"No download URL configured for species '{species.name}'. Please place the transcriptome at {destination}."
        )

    download_path = destination.with_suffix(destination.suffix + ".download")
    _download_stream(url, download_path)

    if download_path.suffix.endswith(".gz"):
        _gunzip(download_path, destination)
    else:
        download_path.rename(destination)

    if not skip_checksum:
        expected = checksums.get(filename)
        if expected and not verify_checksum(destination, expected):
            destination.unlink(missing_ok=True)
            raise ValueError(
                f"Checksum mismatch when downloading {filename}."
            )

    return destination


def _download_stream(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fh.write(chunk)


def _gunzip(archive: Path, destination: Path) -> None:
    with gzip.open(archive, "rb") as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    archive.unlink(missing_ok=True)
