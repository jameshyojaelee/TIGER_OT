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
- `scripts/` – numbered setup/diagnostic/launch helpers
  - `scripts/nt_guides/` – non-targeting guide generation and validation tools
  - `scripts/legacy/` – legacy shims for backward compatibility
- `src/` – Python sources (`lib/`, `workflows/`, native off-target code)
- `vendor/venv_packages/` – optional vendored Python wheels used by the environment wrapper
- `runs/` – default destination for new workflow executions (ignored by git)

## Installation Notes

- Requires Python 3.10+, GCC toolchain, and access to TensorFlow modules on the cluster.
- `scripts/01_setup_workspace.sh` skips `pip` when bundled dependencies under `vendor/venv_packages/` are present; set `TIGER_FORCE_PIP=1` to reinstall or `TIGER_SKIP_PIP=1` to skip explicitly (default). To pull TensorFlow via `pip`, export `TIGER_SKIP_TF_PIP=0`.
- `scripts/01_setup_workspace.sh` still runs `make clean && make`; adjust the pip phase using the environment variables above depending on your cluster policy.
- Provide TIGER model assets under `resources/models/tiger_model/` (symlink or copy). For references, the setup script checks both mouse (`resources/reference/gencode.vM37.transcripts.uc.joined`) and human (`resources/reference/gencode.v47.transcripts.fa`). The human transcriptome is automatically copied from `/gpfs/commons/home/jameslee/reference_genome/refdata-gex-GRCh38-2024-A/genome/gencode.v47.transcripts.fa.gz` if present; otherwise, copy or symlink your lab's version.
- To download new references or models on-demand, use `scripts/fetch_reference.sh` or `scripts/fetch_model.sh`. The latter expects either `TIGER_MODEL_ARCHIVE` (local tar/zip) or `TIGER_MODEL_ARCHIVE_URL` (downloadable archive) and optionally `TIGER_MODEL_ARCHIVE_MD5` for checksum validation.
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
- `scripts/fetch_reference.sh <species> [dest]` – download transcriptome bundles with checksum verification.
- `scripts/fetch_model.sh [model] [dest]` – download and cache TIGER model archives (requires env vars).

## Non-Targeting Guide Design

Non-targeting (NT) guides are essential negative controls in CRISPR screens. Unlike gene-targeting guides, NT guides should not perturb any transcripts in the organism. This workflow provides tools to generate and validate NT guide candidates using the off-target search algorithm.

### Strategy

The NT guide design strategy uses TIGER's off-target detection to ensure candidate sequences have zero complementarity to the transcriptome:

1. **Generate random 23nt sequences** with balanced GC content (40-60%) and no simple repeats
2. **Screen against transcriptome** using the C-based off-target search binary
3. **Select sequences** with MM0=0, MM1=0, MM2=0 (zero perfect matches, 1-mismatch, or 2-mismatch hits)

### Tools

Two scripts are provided in `scripts/nt_guides/`:

- **`generate_nt_candidates.py`** – Generates random 23-nucleotide sequences with quality filters:
  - GC content between 40-60%
  - No homopolymer runs ≥4 (e.g., AAAA, GGGG)
  - No dinucleotide repeats ≥4 (e.g., ATATAT)
  - Ensures sequence uniqueness

- **`test_nt_candidates.py`** – Validates NT candidates against the transcriptome:
  - Runs TIGER's off-target search on candidate sequences
  - Reports MM0, MM1, MM2 counts for each sequence
  - Filters and saves perfect candidates (zero off-targets at all mismatch levels)
  - Outputs detailed CSV reports for analysis

### Quick Start

```bash
# 1. Generate 30 candidate sequences
python3 scripts/nt_guides/generate_nt_candidates.py 30 2>/dev/null | \
  cut -f1 > examples/targets/my_nt_candidates.txt

# 2. Test candidates against mouse transcriptome
# Edit test_nt_candidates.py to point to your candidates file, then:
python3 scripts/nt_guides/test_nt_candidates.py

# 3. Review results
cat runs/nt_validation/perfect_nt_candidates.csv
```

See `scripts/nt_guides/README.md` for detailed documentation and advanced usage.

### Example Usage

```bash
# Generate 50 candidates
python3 scripts/nt_guides/generate_nt_candidates.py 50 2>/dev/null | cut -f1 > examples/targets/my_nt_candidates.txt

# The test script will:
# - Load sequences from the specified file
# - Run off-target analysis (~45 seconds per 3 sequences)
# - Output sequences with zero off-targets
# - Save detailed results to runs/nt_validation/
```

### Pre-validated NT Guides

The repository includes 10 pre-validated mouse NT guides in `examples/targets/NT.txt`. All sequences have been confirmed to have zero MM0, MM1, and MM2 hits against gencode.vM37 mouse transcriptome.

### Output Files

- `runs/nt_validation/nt_candidates_offtarget.csv` – Full off-target analysis with MM0/MM1/MM2 counts
- `runs/nt_validation/perfect_nt_candidates.csv` – Filtered list of sequences with zero off-targets
- `runs/nt_validation/analysis.log` – Complete analysis log

### Notes

- **Guide length**: Fixed at 23 nucleotides (matches TIGER's standard guide length)
- **Species**: Update the `reference_path` in the test script for human designs
- **Runtime**: Approximately 15 seconds per sequence on typical HPC nodes
- **Quality threshold**: Only sequences with MM0=MM1=MM2=0 are recommended as NT controls

## Documentation & Support

- `docs/WORKFLOW_GUIDE.md` – exhaustive playbook with configuration detail.
- `docs/GUIDE_SELECTION_AND_VALIDATION.md` – guide selection process, off-target analysis, and transcript-level validation.
- `docs/WORKFLOW_STATUS.txt` – latest validation snapshot.
- `docs/UPDATE_SUMMARY.txt` – change log.

Issues or questions? Open a ticket in the lab tracker or message the TIGER maintainers on Slack.
