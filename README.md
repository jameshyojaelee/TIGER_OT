# Cas13 TIGER Workflow

End-to-end Cas13 guide design with TIGER scoring, off-target analysis, and adaptive filtering. Run the numbered helper scripts in `scripts/` for a predictable first-time setup.

## Run Order

1. `scripts/01_setup_workspace.sh` – build the C helper, install Python packages, and verify model/reference assets.
2. `scripts/02_quick_check.sh` – lightweight validation after setup.
3. `scripts/03_preflight_check.sh` – comprehensive diagnostics (run before production jobs).
4. `scripts/04_run_workflow.sh targets.txt [options]` – launch the workflow via the environment wrapper.

Optional: `scripts/01b_create_conda_env.sh` creates an isolated conda environment; `scripts/00_load_environment.sh` is the environment wrapper behind the launcher. Legacy scripts at the repo root call into these numbered entrypoints for backward compatibility.

## Quick Start

```bash
cd /gpfs/commons/groups/sanjana_lab/Cas13/TIGER

# 1. Install dependencies and verify assets
scripts/01_setup_workspace.sh

# 2. Run quick validation (repeatable)
scripts/02_quick_check.sh

# 3. Run the full preflight diagnostics
scripts/03_preflight_check.sh

# 4. Prepare targets and launch
cp targets.example.txt targets.txt  # edit to add your genes
scripts/04_run_workflow.sh targets.txt
```

### Smoke Test (bundled)

```bash
scripts/04_run_workflow.sh test_targets.txt --config config.sample.yaml --output-dir output_smoke --skip-validation
head output_smoke/final_guides.csv
```

## Features

- Single-command workflow orchestration with environment isolation
- Fast C offtarget search (10–100× faster than pure Python)
- TIGER integration for ML-based guide scoring
- Adaptive off-target filtering and MM0/MM1/MM2 constraints
- Resume-from checkpoints for long runs
- Detailed logging plus optional validation of MM0 locations

## Installation Notes

- Requires Python 3.10+, GCC toolchain, and access to TensorFlow modules on the cluster.
- `scripts/01_setup_workspace.sh` skips `pip` when bundled dependencies under `venv_packages/` are present; set `TIGER_FORCE_PIP=1` to reinstall or `TIGER_SKIP_PIP=1` to skip explicitly (default). To pull TensorFlow via `pip`, export `TIGER_SKIP_TF_PIP=0`.
- `scripts/01_setup_workspace.sh` still runs `make clean && make`; adjust the pip phase using the environment variables above depending on your cluster policy.
- Provide TIGER model assets under `models/tiger_model/` (symlink or copy) and a reference transcriptome file referenced by `config.yaml` (`reference/gencode.vM37.transcripts.uc.joined` ships as a tiny smoke-test FASTA).
- Optional conda workflow: run `scripts/01b_create_conda_env.sh` first. If the solve is killed (common on shared login nodes), load a newer Anaconda module or skip conda and rely on the provided module wrapper instead.

## Usage

```bash
scripts/04_run_workflow.sh targets.txt [--top-n 5 --config custom.yaml --threads 8]
```

Common flags:
- `--output-dir PATH` – change output location (default `output/`).
- `--config FILE` – alternate configuration (default `config.yaml`).
- `--top-n INT` – guides per gene (default 10).
- `--dry-run` – print execution plan without running steps.
- `--skip-download` – reuse pre-downloaded FASTA files.
- `--skip-validation` – skip MM0 location analysis.
- `--resume-from {download,tiger,offtarget,filter}` – restart from a checkpoint.
- `--threads INT` – adjust parallelism (default 4).

GPU mode: export `TIGER_USE_GPU=1` (and optionally `TIGER_TF_GPU_MODULE`) before calling `scripts/04_run_workflow.sh`.

## Outputs

- `output/final_guides.csv` – final ranked guides.
- `output/workflow.log` – workflow log from the run.
- Additional CSV/JSON artifacts driven by configuration (e.g., MM0 validation reports).

## Diagnostics

- `scripts/02_quick_check.sh` – fast sanity check (rerun after changes).
- `scripts/03_preflight_check.sh` – full nine-part diagnostics (wrapper, Python packages, config, model, reference, binary).

## Documentation & Support

- `WORKFLOW_GUIDE.md` – exhaustive playbook with configuration detail.
- `WORKFLOW_STATUS.txt` – latest validation snapshot.
- `UPDATE_SUMMARY.txt` – change log.

Issues or questions? Open a ticket in the lab tracker or message the TIGER maintainers on Slack.
