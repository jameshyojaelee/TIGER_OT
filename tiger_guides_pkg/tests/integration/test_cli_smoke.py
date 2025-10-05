import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
def test_cli_smoke(tmp_path):
    binary = Path("bin/offtarget_search")
    if not binary.exists():
        pytest.skip("off-target binary not available; skipping CLI smoke test")

    env = dict(**{k: v for k, v in subprocess.os.environ.items()}, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    cmd = [
        "python",
        "-m",
        "tiger_guides.cli",
        "smoke",
    ]
    result = subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    final_csv = tmp_path / "runs" / "smoke" / "final_guides.csv"
    assert final_csv.exists()
