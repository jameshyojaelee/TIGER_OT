# Cas13 TIGER Workflow

```
+-------------+    +------------------+    +------------------+    +----------------------+
| targets.txt | -> | CDS download     | -> | TIGER scoring    | -> | Off-target filtering |
| gene list   |    | (Ensembl REST)   |    | + ranking        |    | + adaptive MM0       |
+-------------+    +------------------+    +------------------+    +----------------------+
                                     |
                                     v
                           runs/<job>/final_guides.csv
```

End-to-end Cas13 guide design with reproducible setup scripts, TIGER ML scoring, fast C off-target search, and adaptive filtering.

## Quick Start Checklist

1. **Clone & enter the repo**
   ```bash
   cd /gpfs/commons/groups/sanjana_lab/Cas13/TIGER
   ```
2. **Bootstrap the workspace (one time per node)**
   ```bash
   scripts/01_setup_workspace.sh
   scripts/02_quick_check.sh
   scripts/03_preflight_check.sh
   ```
3. **Create your targets file**
   ```bash
   cp examples/targets/example_targets.txt targets.txt  # edit with one gene per line
   ```
4. **Launch the workflow**
   ```bash
   scripts/04_run_workflow.sh targets.txt --species mouse
   ```

Smoke test a bundled mini-run:

```bash
scripts/04_run_workflow.sh examples/targets/test_targets.txt \
    --species mouse \
    --config configs/smoke-test.yaml \
    --output-dir runs/smoke \
    --skip-validation
head runs/smoke/final_guides.csv
```

## Workflow Highlights

- Single command launcher wraps environment modules and PYTHONPATH fixes.
- Tens-of-millions off-target queries handled by an optimized C binary (10–100× faster than Python).
- Adaptive MM0/MM1/MM2 filtering and resume-from checkpoints.
- Optional MM0 transcript-level validation for deeper specificity checks.
- GPU toggle (`TIGER_USE_GPU=1`) with support for TensorFlow module overrides.

## Repository Tour

| Path | Contents |
|------|----------|
| `configs/` | Default and smoke-test YAML configurations |
| `docs/` | Playbooks, validation status, change log |
| `examples/` | Targets and archived example runs |
| `resources/` | Bundled TIGER model and transcriptomes |
| `scripts/` | Numbered setup, diagnostics, workflow launchers |
| `scripts/nt_guides/` | Tools for non-targeting control design |
| `src/` | Legacy wrappers and helper utilities |
| `tiger_guides_pkg/` | Primary Python package, C sources, tests |
| `runs/` | Destination for workflow outputs (ignored by git) |

## Running the Pipeline

### 1. Prepare the environment

- Requires Python 3.10+, GCC, and TensorFlow modules on the cluster.
- `scripts/01_setup_workspace.sh` builds native helpers and installs Python dependencies. Control pip behavior via:
  - `TIGER_SKIP_PIP=1` (default when `vendor/venv_packages/` exists)
  - `TIGER_FORCE_PIP=1` to reinstall
  - `TIGER_SKIP_TF_PIP=0` to allow TensorFlow wheels
- Ensure model assets live under `resources/models/tiger_model/`.
- Provide transcriptomes:
  - Mouse default: `resources/reference/gencode.vM37.transcripts.uc.joined`
  - Human default: `resources/reference/gencode.v47.transcripts.fa` (auto-copied from `/gpfs/commons/home/jameslee/reference_genome/...` when available)
  - Use `scripts/fetch_reference.sh` and `scripts/fetch_model.sh` to pull or refresh assets.

### 2. Launch a run

```bash
scripts/04_run_workflow.sh targets.txt \
    --species {mouse|human} \
    [--config configs/custom.yaml] \
    [--top-n 5] \
    [--threads 8]
```

The launcher wraps `scripts/00_load_environment.sh`, purges conflicting modules, and forwards all options to `run_tiger.py`.

### 3. Monitor progress

- Follow `runs/<job>/workflow.log` for stage-by-stage updates.
- Long off-target searches can be resumed with `--resume-from offtarget`.
- Submit to SLURM with the helper wrapper:
  ```bash
  sbatch --job-name=my_run scripts/submit_workflow.sh targets.txt --species mouse
  ```

### 4. Inspect results

- Final guides land at `runs/<job>/final_guides.csv`.
- Intermediate artifacts:
  - `runs/<job>/sequences/all_targets.fasta`
  - `runs/<job>/tiger/guides.csv`
  - `runs/<job>/offtarget/results.csv`
- When `output.validate_mm0_locations=true`, an additional `mm0_location_analysis.csv` is generated (or run `scripts/validate_mm0_locations.py` manually).

### Optional extras

- `--dry-run` prints the planned steps without execution.
- `--skip-download` reuses existing FASTA sequences.
- `--skip-validation` bypasses MM0 location analysis for speed.
- `TIGER_USE_GPU=1` and `TIGER_TF_GPU_MODULE=TensorFlow/<version>` enable GPU runs.

## CLI Flag Reference

| Flag | Description |
|------|-------------|
| `--species {mouse,human}` | Select organism (required) |
| `--output-dir PATH` | Override output directory (default `runs/latest`) |
| `--config FILE` | Alternate configuration YAML |
| `--top-n INT` | Guides per gene (default 10) |
| `--threads INT` | Worker threads (default 4) |
| `--resume-from STEP` | Restart at `download`, `tiger`, `offtarget`, or `filter` |
| `--skip-download` | Reuse existing FASTA sequences |
| `--skip-validation` | Skip MM0 location validation |
| `--dry-run` | Print execution plan only |
| `--verbose/-v` | Increase logging verbosity |

## Outputs at a Glance

- `final_guides.csv` – Ranked, filtered guides (top N per gene).
- `workflow.log` – Timestamped pipeline log.
- `filtering_stats.json` – Counts per filtering stage.
- `mm0_location_analysis.csv` – Transcript-level MM0 audit (when enabled).
- SLURM jobs emit `slurm_<jobid>.out/err` under `runs/<job>/` or `runs/slurm_logs/`.

## Diagnostics & Validation

- `scripts/02_quick_check.sh` – Fast post-setup sanity sweep.
- `scripts/03_preflight_check.sh` – Full nine-part validation (wrapper, Python, configs, model, reference, binary).
- `scripts/validate_mm0_locations.py` – Stand-alone MM0 transcript audit utility.
- `scripts/fetch_reference.sh <species> [dest]` – Retrieve transcriptomes with checksum verification.
- `scripts/fetch_model.sh [model] [dest]` – Download and unpack TIGER model bundles.

## Non-Targeting (NT) Guides

- `scripts/nt_guides/generate_nt_candidates.py` – Produce random 23 nt candidates with GC and repeat filters.
- `scripts/nt_guides/test_nt_candidates.py` – Run off-target screening to keep sequences with MM0=MM1=MM2=0.
- Pre-validated mouse NT controls live in `examples/targets/NT.txt`.
- Outputs: `runs/nt_validation/nt_candidates_offtarget.csv`, `perfect_nt_candidates.csv`, and `analysis.log`.

## Documentation & Support

- `docs/WORKFLOW_GUIDE.md` – Detailed runbook and configuration guidance.
- `docs/GUIDE_SELECTION_AND_VALIDATION.md` – MM0/MM1/MM2 interpretation and transcript-level validation walkthrough.
- `docs/WORKFLOW_STATUS.txt` – Current validation snapshot.
- `docs/UPDATE_SUMMARY.txt` – Recent changes and upgrade notes.


## Cite TIGER

Prediction of on-target and off-target activity of CRISPR–Cas13d guide RNAs using deep learning. Wessels, H.-H.*, Stirn, A.*, Méndez-Mancilla, A., Kim, E. J., Hart, S. K., Knowles, D. A.#, & Sanjana, N. E.# Nature Biotechnology (2023). https://doi.org/10.1038/s41587-023-01830-8

## Off-Target Workflow: Differences vs Original Code

- Original source reference: `/gpfs/commons/groups/sanjana_lab/oahmed/naive_guide_to_ref_code/`

What changed compared to the original C programs (`guide_to_ref_cas13*`)?

- Search engine and I/O
  - Original: memory-maps a preprocessed reference string with `X` sentinels between transcripts and requires three inputs: joined reference, query file (one sequence per line, batches of 5), and a mapping file (seq→gene or seq→transcript). Outputs per-query counts and a pipe-delimited list of MM0 gene/transcript names.
  - Ours: C binary `bin/offtarget_search` reads a CSV with `Gene,Sequence` and a standard FASTA transcriptome. Outputs one row per guide with `MM0..MM5` plus `MM0_Transcripts` and `MM0_Genes` (pipe-delimited). Wrapper merges counts back onto the TIGER guides by `Gene` and `Sequence`.

- Parallelism and batching
  - Original: fixed 5-query SIMD “pipeline”; users split queries manually (e.g., 1,500 per file) and manage SLURM scripts.
  - Ours: AVX2 + OpenMP in C (thread override via `TIGER_OFFTARGET_THREADS`) and Python-side chunking/SLURM helpers. No multiple-of-5 requirement; arbitrary guide counts are supported.

- Query length handling
  - Original: effectively hard-coded to 23 nt (see fixed mask/popcount for 23 bases).
  - Ours: supports variable lengths up to 30 nt, masking comparisons by actual guide length.

- Boundary handling over concatenated reference
  - Original: tracks `in_seq` state and increments sequence index when encountering `X` sentinels during scanning.
  - Ours: precomputes a boolean array of valid start positions requiring `max_guide_len` non-`X` bases, avoiding partial overlaps across sentinels.

- MM0 locations (where perfect matches occur)
  - Original: directly collects gene/transcript names for MM0 hits during the scan using the provided mapping file; writes them to output.
  - Ours: the C pass now emits the same information (pipe-delimited transcript + gene columns) without requiring external mapping files. The optional Python validation step (`mm0_location_analysis.csv`) still provides deeper summaries (same-gene vs cross-gene breakdowns) on the filtered guide set.

- Filtering and ranking logic (new)
  - Adaptive MM0 per gene with tolerance: keep guides with `MM0` in `[min_MM0, min_MM0 + tolerance]` (configurable, default 3). This balances specificity vs availability when genes have many isoforms.
  - Enforce `MM1 <= threshold` and `MM2 <= threshold` (defaults 0) and `MM0 >= 1`.
  - Rank by TIGER score and select top-N per gene (configurable).

- Orchestration and species awareness
  - Original: standalone binaries and manual preprocessing of inputs (join references, make mapping files, split queries, write SLURM).
  - Ours: a single CLI runs download → TIGER scoring → off-target search → adaptive filtering with species-specific transcriptomes and resume-from checkpoints.

Key implementation touchpoints in this repo

- C off-target search: `src/lib/offtarget/search.c:1` (AVX2 + OpenMP counting of MM0..MM5 with variable-length masking and sentinel-aware valid windows)
- Python wrapper: `tiger_guides_pkg/src/tiger_guides/offtarget/search.py:1` (chunking, SLURM array helper, merge results)
- Filtering logic: `tiger_guides_pkg/src/tiger_guides/filters/ranking.py:1` (MM1/MM2 thresholds, `MM0>=1`, adaptive MM0 tolerance, top-N per gene)
- Workflow runner: `tiger_guides_pkg/src/tiger_guides/workflow/runner.py:1` (end-to-end orchestration and config wiring)
- MM0 location validation (optional): `tiger_guides_pkg/src/tiger_guides/tiger/validation.py:1`

Notes on behavioral differences

- Output schema now mirrors the legacy format (counts + MM0 transcript/gene columns) while remaining compatible with downstream filtering.
- No manual batching constraints; guide counts need not be multiple of 5.
- Defaults prioritize specificity (`MM1=0`, `MM2=0`) with a configurable, adaptive MM0 window.

Original code pointers for comparison

- Binaries and sources: `/gpfs/commons/groups/sanjana_lab/oahmed/naive_guide_to_ref_code/src` (e.g., `guide_to_ref_cas13_with_transcripts.c`, `guide_to_ref_cas13_with_genes.c`)
- Usage and preprocessing docs: `/gpfs/commons/groups/sanjana_lab/oahmed/naive_guide_to_ref_code/track_dataset_v2` and `track_dataset_v3`
