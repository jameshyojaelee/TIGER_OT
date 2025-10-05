"""SLURM utilities for tiger_guides."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Iterable, Optional


def submit_slurm_job(script_path: Path, job_name: Optional[str] = None, account: Optional[str] = None,
                     partition: Optional[str] = None, time_limit: Optional[str] = None,
                     mem: Optional[str] = None, cpus: int = 1, dependency: Optional[str] = None) -> int:
    cmd = ["sbatch"]
    if job_name:
        cmd.extend(["--job-name", job_name])
    if account:
        cmd.extend(["--account", account])
    if partition:
        cmd.extend(["--partition", partition])
    if time_limit:
        cmd.extend(["--time", time_limit])
    if mem:
        cmd.extend(["--mem", mem])
    if cpus > 1:
        cmd.extend(["--cpus-per-task", str(cpus)])
    if dependency:
        cmd.extend(["--dependency", dependency])
    cmd.append(str(script_path))

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"SLURM submission failed: {result.stderr}")

    for token in result.stdout.split():
        if token.isdigit():
            return int(token)
    raise RuntimeError(f"Could not parse job ID from sbatch output: {result.stdout}")


def check_job_status(job_id: int) -> str:
    cmd = ["squeue", "-j", str(job_id), "-h", "-o", "%T"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\n")[0]

    cmd = ["sacct", "-j", str(job_id), "-n", "-o", "State"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\n")[0]
    return "UNKNOWN"


def wait_for_jobs(job_ids: Iterable[int], poll_interval: int = 30, logger=None) -> bool:
    job_ids = list(job_ids)
    pending = set(job_ids)

    while pending:
        time.sleep(poll_interval)
        completed = set()

        for job_id in pending:
            status = check_job_status(job_id)
            if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"}:
                completed.add(job_id)
                if logger:
                    if status == "COMPLETED":
                        logger.info(f"✅ Job {job_id} completed")
                    else:
                        logger.error(f"❌ Job {job_id} finished with status {status}")

        pending -= completed
        if pending and logger:
            logger.info(f"⏳ {len(pending)} job(s) still running...")

    return all(check_job_status(job_id) == "COMPLETED" for job_id in job_ids)


def cancel_jobs(job_ids: Iterable[int], logger=None) -> None:
    for job_id in job_ids:
        subprocess.run(["scancel", str(job_id)], capture_output=True)
        if logger:
            logger.info(f"Cancelled job {job_id}")


__all__ = [
    "submit_slurm_job",
    "check_job_status",
    "wait_for_jobs",
    "cancel_jobs",
]
