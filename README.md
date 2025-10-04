# Cas13 TIGER Workflow

End-to-end Cas13 guide design with TIGER scoring, off-target analysis, and adaptive filtering. Run the numbered helper scripts in `scripts/` for a predictable first-time setup.

## Run Order

1. `scripts/01_setup_workspace.sh` – build the C helper, install Python packages, and verify model/reference assets.
2. `scripts/02_quick_check.sh` – lightweight validation after setup.
3. `scripts/03_preflight_check.sh` – comprehensive diagnostics (run before production jobs).
4. `scripts/04_run_workflow.sh targets.txt [options]` – launch the workflow via the environment wrapper.

Optional: `scripts/01b_create_conda_env.sh` creates an isolated conda environment; `scripts/00_load_environment.sh` is the environment wrapper behind the launcher. Legacy shims now live under `scripts/legacy/` and forward to the numbered entrypoints for backward compatibility.

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
cp examples/targets/example_targets.txt targets.txt  # edit to add your genes
scripts/04_run_workflow.sh targets.txt --species mouse
```

### Smoke Test (bundled)

```bash
scripts/04_run_workflow.sh examples/targets/test_targets.txt --species mouse --config configs/smoke-test.yaml --output-dir runs/smoke --skip-validation
head runs/smoke/final_guides.csv
```

## Features

- Single-command workflow orchestration with environment isolation
- Fast C offtarget search (10–100× faster than pure Python)
- TIGER integration for ML-based guide scoring
- Adaptive off-target filtering and MM0/MM1/MM2 constraints
- Resume-from checkpoints for long runs
- Detailed logging plus optional validation of MM0 locations

## Repository Layout

- `configs/` – versioned defaults and smoke-test configurations
- `docs/` – guides, status reports, and changelog
- `examples/` – sample targets plus archived run outputs
- `resources/` – bundled models and reference transcriptomes
- `scripts/` – numbered setup/diagnostic/launch helpers (`scripts/legacy/` keeps old shims)
- `src/` – Python sources (`lib/`, `workflows/`, native off-target code)
- `vendor/venv_packages/` – optional vendored Python wheels used by the environment wrapper
- `runs/` – default destination for new workflow executions (ignored by git)

## Installation Notes

- Requires Python 3.10+, GCC toolchain, and access to TensorFlow modules on the cluster.
- `scripts/01_setup_workspace.sh` skips `pip` when bundled dependencies under `vendor/venv_packages/` are present; set `TIGER_FORCE_PIP=1` to reinstall or `TIGER_SKIP_PIP=1` to skip explicitly (default). To pull TensorFlow via `pip`, export `TIGER_SKIP_TF_PIP=0`.
- `scripts/01_setup_workspace.sh` still runs `make clean && make`; adjust the pip phase using the environment variables above depending on your cluster policy.
- Provide TIGER model assets under `resources/models/tiger_model/` (symlink or copy). For references, the setup script checks both mouse (`resources/reference/gencode.vM37.transcripts.uc.joined`) and human (`resources/reference/gencode.v47.transcripts.fa`). The human transcriptome is automatically copied from `/gpfs/commons/home/jameslee/reference_genome/refdata-gex-GRCh38-2024-A/genome/gencode.v47.transcripts.fa.gz` if present; otherwise, copy or symlink your lab's version.
- Optional conda workflow: run `scripts/01b_create_conda_env.sh` first. If the solve is killed (common on shared login nodes), load a newer Anaconda module or skip conda and rely on the provided module wrapper instead.

## Usage

```bash
scripts/04_run_workflow.sh targets.txt --species {mouse,human} [--top-n 5 --config configs/custom.yaml --threads 8]
```

Common flags:
- `--species {mouse,human}` – **required**; selects the organism (`mouse` → `mus_musculus`, `human` → `homo_sapiens`).
- `--output-dir PATH` – change output location (default `runs/latest`).
- `--config FILE` – alternate configuration (default `configs/default.yaml`).
- `--top-n INT` – guides per gene (default 10).
- `--dry-run` – print execution plan without running steps.
- `--skip-download` – reuse pre-downloaded FASTA files.
- `--skip-validation` – skip MM0 location analysis.
- `--resume-from {download,tiger,offtarget,filter}` – restart from a checkpoint.
- `--threads INT` – adjust parallelism (default 4).

GPU mode: export `TIGER_USE_GPU=1` (and optionally `TIGER_TF_GPU_MODULE`) before calling `scripts/04_run_workflow.sh`.

## Outputs

- `runs/<name>/final_guides.csv` – final ranked guides.
- `runs/<name>/workflow.log` – workflow log from the run.
- Additional CSV/JSON artifacts driven by configuration (e.g., MM0 validation reports).

## Diagnostics

- `scripts/02_quick_check.sh` – fast sanity check (rerun after changes).
- `scripts/03_preflight_check.sh` – full nine-part diagnostics (wrapper, Python packages, config, model, reference, binary).

## Documentation & Support

- `docs/WORKFLOW_GUIDE.md` – exhaustive playbook with configuration detail.
- `docs/WORKFLOW_STATUS.txt` – latest validation snapshot.
- `docs/UPDATE_SUMMARY.txt` – change log.

Issues or questions? Open a ticket in the lab tracker or message the TIGER maintainers on Slack.
