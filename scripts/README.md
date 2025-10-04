# TIGER workflow scripts

Run the numbered scripts in order when setting up a fresh checkout:

1. `scripts/01_setup_workspace.sh` – build C extensions, install Python deps, verify assets.
2. `scripts/02_quick_check.sh` – fast post-setup validation.
3. `scripts/03_preflight_check.sh` – full diagnostics (use before production runs).
4. `scripts/04_run_workflow.sh` – launch the Cas13 TIGER workflow.

> `scripts/04_run_workflow.sh` now requires `--species {mouse,human}`. Choose `mouse` for `mus_musculus` or `human` for `homo_sapiens` runs.

Optional helpers:
- `scripts/00_load_environment.sh` – environment wrapper that backs the workflow launcher.
- `scripts/01b_create_conda_env.sh` – provision an isolated conda environment.

Legacy entrypoints now live under `scripts/legacy/` (`setup.sh`, `preflight_check.sh`, `run_tiger_workflow.sh`, etc.) and forward to the numbered scripts to keep older documentation working.

Environment toggles for `scripts/01_setup_workspace.sh`:
- `TIGER_SKIP_PIP=1` (default when `vendor/venv_packages/` exists) – skip installing packages with pip
- `TIGER_FORCE_PIP=1` – force pip even if bundles exist
- `TIGER_SKIP_TF_PIP=0` – include TensorFlow/Keras in the pip install
- `TIGER_PIP_SCOPE=system` / `TIGER_PIP_TARGET=/path` – choose installation location
