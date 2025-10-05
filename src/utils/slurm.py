"""Legacy SLURM helpers bridging to existing utilities."""
import sys
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists() and str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

try:  # pragma: no cover - prefer shared implementation if available
    from tiger_guides.slurm import (
        submit_slurm_job,
        check_job_status,
        wait_for_jobs,
        cancel_jobs,
    )
except ModuleNotFoundError:
    from lib.utils.slurm import (
        submit_slurm_job,
        check_job_status,
        wait_for_jobs,
        cancel_jobs,
    )

__all__ = [
    "submit_slurm_job",
    "check_job_status",
    "wait_for_jobs",
    "cancel_jobs",
]
