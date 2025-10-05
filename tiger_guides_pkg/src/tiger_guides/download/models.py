"""Model asset management utilities."""
from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

import requests

from ..constants import MODEL_CATALOG
from .checksums import verify_checksum, md5sum

CHUNK_SIZE = 1024 * 1024


def ensure_model(model_key: str, cache_root: Path) -> Path:
    """Ensure a model bundle is available locally.

    Parameters
    ----------
    model_key: str
        Key inside ``MODEL_CATALOG`` (currently only ``"tiger"``).
    cache_root: Path
        Directory where the model should be cached/extracted.
    """
    if model_key not in MODEL_CATALOG:
        raise ValueError(f"Unknown model '{model_key}'. Known models: {', '.join(MODEL_CATALOG)}")

    meta = MODEL_CATALOG[model_key]
    target_dir = cache_root / meta["target_dir"]
    target_dir = target_dir.resolve()

    if _model_ready(target_dir, meta["required_files"]):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    archive = _locate_archive(meta)
    if archive is None:
        raise FileNotFoundError(
            "Model archive not provided. Set either TIGER_MODEL_ARCHIVE (local path) or "
            "TIGER_MODEL_ARCHIVE_URL (download URL)."
        )

    archive_path = _materialise_archive(archive, cache_root)

    expected_md5 = os.environ.get(meta.get("md5_env", ""))
    if expected_md5 and not verify_checksum(archive_path, expected_md5.lower()):
        archive_path.unlink(missing_ok=True)
        raise ValueError("Model archive checksum mismatch. Download/copy again.")

    _extract_archive(archive_path, target_dir)

    if not _model_ready(target_dir, meta["required_files"]):
        raise RuntimeError(f"Model extraction incomplete for {model_key} (expected files missing).")

    return target_dir


def _model_ready(target_dir: Path, required_files) -> bool:
    if not target_dir.exists():
        return False
    for rel in required_files:
        if not (target_dir / rel).exists():
            return False
    return True


def _locate_archive(meta) -> Optional[str]:
    local_path = os.environ.get(meta.get("archive_env", ""))
    if local_path:
        return local_path
    url = os.environ.get(meta.get("url_env", ""))
    if url:
        return url
    return None


def _materialise_archive(source: str, cache_root: Path) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    if source.startswith("http://") or source.startswith("https://"):
        archive_path = cache_root / Path(source).name
        if archive_path.exists():
            return archive_path
        _download_stream(source, archive_path)
        return archive_path
    else:
        src_path = Path(source)
        if not src_path.exists():
            raise FileNotFoundError(f"Model archive not found: {source}")
        dest = cache_root / src_path.name
        if src_path.resolve() != dest.resolve():
            if dest.exists():
                return dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(src_path, dest)
        return dest


def _download_stream(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fh.write(chunk)


def _extract_archive(archive: Path, target_dir: Path) -> None:
    suffix = archive.suffix.lower()
    if suffix in {".gz", ".tgz", ".tar"}:
        mode = "r:gz" if suffix == ".gz" or archive.name.endswith(".tar.gz") else "r"
        with tarfile.open(archive, mode) as tar:
            tar.extractall(path=target_dir)
    elif suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(target_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive}")
