# Streamlit TIGER UI – Quick Deployment (In-Network Access)

This short playbook explains how to launch the TIGER Streamlit server on the NYGC HPC and let other lab members browse it on the internal network (or via an SSH tunnel).

---

## 1. Prerequisites

- TIGER repo checked out at `/gpfs/commons/groups/sanjana_lab/Cas13/TIGER`
- Virtual environment with dependencies: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Streamlit UI file: `apps/streamlit_tiger.py`
- SLURM script: `slurm_jobs/streamlit_tiger.slurm`

---

## 2. Start the SLURM service

Submit the long-running job:

```bash
sbatch slurm_jobs/streamlit_tiger.slurm
```

Key script defaults:
- Partition: `interactive`
- Resources: 8 CPUs, 32 GB RAM, 7-day walltime
- Port: `8501` (change by setting `STREAMLIT_PORT=XXXX sbatch ...`)
- Logs: `runs/streamlit_logs/tiger_streamlit_<jobid>.out` and `.log`

Check queue status:

```bash
squeue -u $USER -n tiger_streamlit
```

---

## 3. Share the URL

Once the job starts, tail the banner:

```bash
tail -n 40 runs/streamlit_logs/tiger_streamlit_<jobid>.out
```

You’ll see:

```
 Node:      ne1dc3-011.nygenome.org
 Port:      8501
```

- On the internal network (NYGC LAN/VPN): open `http://ne1dc3-011.nygenome.org:8501`
- Off-network: first tunnel through the login node:
  ```bash
  ssh -L 8501:ne1dc3-011.nygenome.org:8501 your_user@ne1dc5-003.nygenome.org
  ```
  Then visit `http://localhost:8501`

No additional authentication is configured—sharing the node hostname and port is enough for trusted users.

---

## 4. Monitoring & shutdown

- Streamlit logs stream to `runs/streamlit_logs/streamlit_<jobid>.log`
- To stop the service: `scancel <jobid>`
- To restart, submit the SLURM script again

If the node reboots or the job hits walltime, the service stops. Re-submit the job to relaunch.

---

## 5. Quick Troubleshooting

| Symptom | Fix |
|---------|-----|
| Browser spins / can’t connect | Verify job is running (`squeue`), ensure you’re on the NYGC network or using an SSH tunnel, confirm port matches the banner |
| “Command not found: streamlit” | Activate `.venv` and reinstall requirements before submitting |
| Permission denied on logs | Make sure `runs/streamlit_logs/` exists and is writeable |
| Need a different port | `STREAMLIT_PORT=8600 sbatch slurm_jobs/streamlit_tiger.slurm` |

For repeated use consider a helper alias:

```bash
alias launch_tiger_streamlit='cd /gpfs/.../TIGER && sbatch slurm_jobs/streamlit_tiger.slurm'
```

---

Happy guide designing! Let the team know the hostname/port and they can jump straight in.
