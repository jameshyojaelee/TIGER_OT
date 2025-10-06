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
- `scripts/validate_mm0_locations.py` – analyze transcript-level matches for final guides (see below).

Specialized workflows:
- `scripts/nt_guides/` – non-targeting guide generation and validation tools.

Legacy entrypoints now live under `scripts/legacy/` (`setup.sh`, `preflight_check.sh`, `run_tiger_workflow.sh`, etc.) and forward to the numbered scripts to keep older documentation working.

Environment toggles for `scripts/01_setup_workspace.sh`:
- `TIGER_SKIP_PIP=1` (default when `vendor/venv_packages/` exists) – skip installing packages with pip
- `TIGER_FORCE_PIP=1` – force pip even if bundles exist
- `TIGER_SKIP_TF_PIP=0` – include TensorFlow/Keras in the pip install
- `TIGER_PIP_SCOPE=system` / `TIGER_PIP_TARGET=/path` – choose installation location

---

## MM0 Location Validation

After running the workflow, use `validate_mm0_locations.py` to analyze exactly which transcripts your guides match:

### Why Validate MM0 Locations?

The standard off-target search counts MM0 (perfect matches) but **doesn't tell you where they are**:
- ✅ **MM0=3** could mean: 3 isoforms of your target gene (GOOD)
- ⚠️ **MM0=3** could mean: 1 target + 2 off-target genes (BAD)

The validation script identifies the exact transcripts and distinguishes these cases.

### Usage

```bash
# Basic usage (uses default mouse reference)
python3 scripts/validate_mm0_locations.py runs/latest/final_guides.csv

# Custom reference and output
python3 scripts/validate_mm0_locations.py runs/my_run/final_guides.csv \
    --reference resources/reference/gencode.vM37.transcripts.fa \
    --output runs/my_run/mm0_detailed.csv

# Human guides
python3 scripts/validate_mm0_locations.py runs/human/final_guides.csv \
    --reference resources/reference/gencode.v47.transcripts.fa
```

### Output

Creates a CSV with transcript-level details:
- **Category**: `SAME_GENE_ONLY` (safe) or `DIFFERENT_GENES` (concerning)
- **Matching Transcripts**: e.g., "Actb-201, Actb-202, Actb-203"
- **Other Gene Transcripts**: Off-target genes (if any)
- **Occurrences per transcript**: Detailed counts

### Interpretation

See [docs/GUIDE_SELECTION_AND_VALIDATION.md](../docs/GUIDE_SELECTION_AND_VALIDATION.md) for detailed guide on:
- Understanding SAME_GENE_ONLY vs DIFFERENT_GENES
- How to handle guides with off-target matches
- Case studies and examples
