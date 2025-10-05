import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _restore_cwd(tmp_path, monkeypatch):
    # Ensure tests run from an isolated working directory
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield
    finally:
        os.chdir(original_cwd)
