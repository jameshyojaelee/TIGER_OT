from pathlib import Path

from tiger_guides.config import SpeciesOption
from tiger_guides.download.references import ensure_reference


def test_ensure_reference_smoke(tmp_path):
    path = ensure_reference(SpeciesOption("mouse"), cache_dir=tmp_path)
    assert path.exists()
    assert path.parent == tmp_path
