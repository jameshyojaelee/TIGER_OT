# TIGER workflow scripts

Run the numbered scripts in order when setting up a fresh checkout:

1. `scripts/01_setup_workspace.sh` – build C extensions, install Python deps, verify assets.
2. `scripts/02_quick_check.sh` – fast post-setup validation.
3. `scripts/03_preflight_check.sh` – full diagnostics (use before production runs).
4. `scripts/04_run_workflow.sh` – launch the Cas13 TIGER workflow.

Optional helpers:
- `scripts/00_load_environment.sh` – environment wrapper that backs the workflow launcher.
- `scripts/01b_create_conda_env.sh` – provision an isolated conda environment.

Legacy entrypoints (`setup.sh`, `preflight_check.sh`, `run_tiger_workflow.sh`, etc.) now point to these numbered scripts to keep older documentation working.
