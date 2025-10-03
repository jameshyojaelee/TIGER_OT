"""
SLURM utilities for job submission and management
"""
import subprocess
import time
from pathlib import Path
import re

def submit_slurm_job(script_path, job_name=None, account=None, partition=None, 
                     time_limit=None, mem=None, cpus=1, dependency=None):
    """
    Submit a SLURM job
    
    Args:
        script_path: Path to SLURM script
        job_name: Job name
        account: SLURM account
        partition: SLURM partition
        time_limit: Time limit (HH:MM:SS)
        mem: Memory requirement
        cpus: Number of CPUs
        dependency: Job dependency (e.g., "afterok:12345")
        
    Returns:
        int: Job ID
    """
    cmd = ['sbatch']
    
    if job_name:
        cmd.extend(['--job-name', job_name])
    if account:
        cmd.extend(['--account', account])
    if partition:
        cmd.extend(['--partition', partition])
    if time_limit:
        cmd.extend(['--time', time_limit])
    if mem:
        cmd.extend(['--mem', mem])
    if cpus > 1:
        cmd.extend(['--cpus-per-task', str(cpus)])
    if dependency:
        cmd.extend(['--dependency', dependency])
    
    cmd.append(str(script_path))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"SLURM submission failed: {result.stderr}")
    
    # Extract job ID from output
    match = re.search(r'Submitted batch job (\d+)', result.stdout)
    if match:
        return int(match.group(1))
    else:
        raise RuntimeError(f"Could not parse job ID from: {result.stdout}")

def check_job_status(job_id):
    """
    Check status of a SLURM job
    
    Args:
        job_id: Job ID
        
    Returns:
        str: Job status (PENDING, RUNNING, COMPLETED, FAILED, etc.)
    """
    cmd = ['squeue', '-j', str(job_id), '-h', '-o', '%T']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        # Job not in queue - check sacct
        cmd = ['sacct', '-j', str(job_id), '-n', '-o', 'State']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return 'UNKNOWN'
    
    status = result.stdout.strip().split('\n')[0] if result.stdout.strip() else 'UNKNOWN'
    return status

def wait_for_jobs(job_ids, poll_interval=30, logger=None):
    """
    Wait for SLURM jobs to complete
    
    Args:
        job_ids: List of job IDs
        poll_interval: Seconds between status checks
        logger: Optional logger
        
    Returns:
        bool: True if all jobs completed successfully
    """
    if logger:
        logger.info(f"Waiting for {len(job_ids)} SLURM jobs to complete...")
    
    pending_jobs = set(job_ids)
    
    while pending_jobs:
        time.sleep(poll_interval)
        
        completed = set()
        for job_id in pending_jobs:
            status = check_job_status(job_id)
            
            if status in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT']:
                completed.add(job_id)
                
                if logger:
                    if status == 'COMPLETED':
                        logger.info(f"✅ Job {job_id} completed")
                    else:
                        logger.error(f"❌ Job {job_id} {status}")
        
        pending_jobs -= completed
        
        if pending_jobs and logger:
            logger.info(f"⏳ {len(pending_jobs)} jobs still running...")
    
    # Check if all jobs completed successfully
    all_success = all(check_job_status(jid) == 'COMPLETED' for jid in job_ids)
    return all_success

def cancel_jobs(job_ids, logger=None):
    """
    Cancel SLURM jobs
    
    Args:
        job_ids: List of job IDs to cancel
        logger: Optional logger
    """
    for job_id in job_ids:
        cmd = ['scancel', str(job_id)]
        subprocess.run(cmd, capture_output=True)
        
        if logger:
            logger.info(f"Cancelled job {job_id}")
