# Cas13 TIGER Workflow Playbook

**Last Updated:** 2025-09-30  
**Status:** ✅ Production ready; wrapper, model, and filters verified end-to-end

---

## Table of Contents
1. [Quick Launch](#quick-launch)
2. [Environment & Setup](#environment--setup)
3. [Workflow Overview](#workflow-overview)
4. [Core Commands](#core-commands)
5. [Outputs & Data Management](#outputs--data-management)
6. [Configuration & Tuning](#configuration--tuning)
7. [Filtering Engine Details](#filtering-engine-details)
8. [Validation & Quality Control](#validation--quality-control)
9. [Troubleshooting](#troubleshooting)
10. [Enhancements (2025-09-30)](#enhancements-2025-09-30)
11. [Best Practices](#best-practices)
12. [Developing & Extending](#developing--extending)
13. [References & Support](#references--support)

---

## Quick Launch

### At a Glance
- ✅ Nine-part pre-flight passed (wrapper, Python 3.12.3, all packages, TIGER core + model, workflow script, config, off-target binary)
- 📂 Run directory: `/gpfs/commons/groups/sanjana_lab/Cas13/TIGER`
- 🧪 Wrapper enforces correct TensorFlow environment and PYTHONPATH

### One-Minute Start
```bash
cd /gpfs/commons/groups/sanjana_lab/Cas13/TIGER

# Create a targets file
cat > my_targets.txt <<'EOF'
Nanog
Sox2
Pou5f1
Klf4
EOF

# Run the workflow (single-line launcher)
scripts/04_run_workflow.sh my_targets.txt

# Inspect results
head output/final_guides.csv
```

### What to Expect
- Final guides saved to `output/final_guides.csv`
- Workflow log at `output/workflow.log`
- Default selection: top 10 high-scoring guides per gene meeting MM criteria

### Success Checklist
- [x] `./preflight_check.sh` reports 9/9 tests passing
- [x] Targets file prepared and reviewed
- [x] `config.yaml` validated for this run
- [x] Single-line launcher used for every run
- [x] Optional dry run completed before large jobs

### Smoke Test (Bundled)
For a quick verification that ships with the repo, use the tiny reference + sample config:

```bash
scripts/04_run_workflow.sh test_targets.txt --config config.sample.yaml --output-dir output_smoke --skip-validation
```

Results land in `output_smoke/final_guides.csv` and the run finishes in under a minute.

---

## Environment & Setup

### Single-Line Launcher
Always launch the workflow through `run_tiger_workflow.sh`; it configures the TIGER environment (purges conflicting modules, loads `TensorFlow/2.15.1-base`, and sets CPU-only TensorFlow flags) before delegating to the Python driver.

```bash
scripts/04_run_workflow.sh targets.txt
```

Behind the scenes the launcher:
- Loads the TensorFlow environment and disables oneDNN custom ops
- Clears CUDA visibility for consistent CPU execution (unless GPU mode is requested)
- Adds `venv_packages/` libraries to `PYTHONPATH`
- Calls `run_with_tiger_env.sh` under the hood for advanced chaining compatibility

> Note: `reference/gencode.vM37.transcripts.uc.joined` ships as a tiny two-transcript FASTA so smoke tests work anywhere. Replace it or point `config.yaml` to a full transcriptome before production runs.

#### GPU mode
Need GPUs? export `TIGER_USE_GPU=1` (and, if required on your cluster, `TIGER_TF_GPU_MODULE` with the TensorFlow module that includes CUDA) before running:

```bash
TIGER_USE_GPU=1 TIGER_TF_GPU_MODULE=TensorFlow/2.15.1-gpu scripts/04_run_workflow.sh targets.txt --threads 8
```

When `TIGER_USE_GPU` is unset, the wrapper forces CPU execution and suppresses the duplicate CUDA plugin warnings you may have noticed earlier.

### Local Dependencies
```
venv_packages/
├── pyyaml/
├── biopython/
├── requests/
├── colorama/
├── tqdm/
└── ... (other runtime dependencies)
```
TensorFlow is provided via the module; Python packages are bundled locally to keep the installation self-contained.

### Health Checks
Run the bundled diagnostics whenever the environment changes:
```bash
./preflight_check.sh
```
The script verifies executable permissions, Python availability, package imports, TIGER assets, configuration validity, and the off-target binary.

---

## Workflow Overview

### End-to-End Stages
1. **Download** – Fetch CDS sequences for each target gene from Ensembl (REST API)
2. **TIGER prediction** – Generate all possible 23-mer guides and score them with the local TIGER TensorFlow model
3. **Off-target search** – Count perfect and mismatched hits (MM0–MM5) against the transcriptome
4. **Filter & rank** – Multi-step filtering pipeline:
   - 4.1 Filter by TIGER score (default ≥ 0.80)
   - 4.2 Enforce MM0 ≥ 1, MM1 = 0, MM2 = 0
   - 4.3 Apply adaptive MM0 with tolerance (min_MM0 → min_MM0 + 3)
   - 4.4 Sort and retain top `top_n_guides` per gene by score
5. **Validate (optional)** – Analyze MM0 hit locations when enabled

### Example Output Row
```csv
Gene,Sequence,Score,Position,MM0,MM1,MM2,MM3,MM4,MM5
Nanog,TGATCACACAGACAACCACCAGC,0.992,123,4,0,0,5,12,34
```

---

## Core Commands

### Primary Entry Points
```bash
# Show CLI options
scripts/04_run_workflow.sh --help

# Dry run (prints plan, no execution)
scripts/04_run_workflow.sh targets.txt --dry-run

# Main execution (default settings)
scripts/04_run_workflow.sh targets.txt
```

### Common Variants
```bash
# Request fewer guides per gene
scripts/04_run_workflow.sh my_targets.txt --top-n 5

# Custom configuration file
scripts/04_run_workflow.sh my_targets.txt --config alt_config.yaml

# Resume after resolving an issue
scripts/04_run_workflow.sh my_targets.txt --resume-from offtarget

# Increase verbosity for debugging
scripts/04_run_workflow.sh my_targets.txt --verbose
```

### Example End-to-End Session
```bash
# Create a quick smoke-test set
cat > test_targets.txt <<'EOF'
Nanog
Sox2
EOF

# Execute the workflow
scripts/04_run_workflow.sh test_targets.txt --verbose

# Inspect key artifacts
cut -d',' -f1 output/final_guides.csv | tail -n +2 | sort | uniq -c
awk -F',' 'NR>1 {print $3}' output/final_guides.csv | sort -n | head -10
```

---

## Outputs & Data Management

### Directory Layout
```
output/
├── sequences/
│   └── all_targets.fasta        # Downloaded CDS sequences
├── tiger/
│   └── guides.csv               # All scored guides
├── offtarget/
│   └── results.csv              # MM0–MM5 counts
├── final_guides.csv             # ⭐ Final per-gene selections
├── mm0_location_analysis.csv    # Optional MM0 location audit
├── config.yaml                  # Snapshot of run configuration
└── workflow.log                 # Full execution log
```

### Operational Tips
- Keep intermediate files (`tiger/`, `offtarget/`) for troubleshooting or reruns
- Archive `workflow.log` with results to preserve provenance
- Copy the exact `config.yaml` used into any report or manuscript

---

## Configuration & Tuning

### `config.yaml` Snapshot (defaults)
```yaml
filtering:
  top_n_guides: 10
  min_guide_score: 0.80   # Filter by TIGER score first
  mm0_tolerance: 3        # Permit MM0 up to min_MM0 + 3
  mm1_threshold: 0        # No 1-mismatch off-targets
  mm2_threshold: 0        # No 2-mismatch off-targets
  adaptive_mm0: true      # Enforce gene-specific minimum MM0

output:
  validate_mm0_locations: true  # Deep dive into MM0 hits
```

### Tuning Playbook
- **Higher confidence only**
  ```yaml
  filtering:
    min_guide_score: 0.85
    mm0_tolerance: 0
  ```
- **Rescue difficult genes**
  ```yaml
  filtering:
    min_guide_score: 0.70
    mm0_tolerance: 5
  ```
- **Disable MM0 validation for speed**
  ```yaml
  output:
    validate_mm0_locations: false
  ```

### Recommended Presets
- **High specificity** (strict off-target control)
  ```yaml
  filtering:
    mm1_threshold: 0
    mm2_threshold: 0
    adaptive_mm0: true
    mm0_tolerance: 0
  ```
- **Maximize guide count** (exploratory screens)
  ```yaml
  filtering:
    min_guide_score: 0.70
    mm1_threshold: 1
    mm2_threshold: 5
    adaptive_mm0: false
  ```

### Additional Sections
```yaml
# TIGER scoring
tiger:
  model_path: "models/tiger_model"
  batch_size: 500
  guide_length: 23
  context_5p: 3
  context_3p: 0

# Off-target search
offtarget:
  reference_transcriptome: "reference/gencode.vM37.transcripts.uc.joined"
  max_mismatches: 5
  chunk_size: 1500

# Output controls
output:
  save_intermediate: true
  compress_logs: false
  generate_plots: true
```

---

## Filtering Engine Details

### Four-Step Selection Pipeline
1. **Score gate**
   ```python
   high_score = df[df["Score"] >= 0.80]
   ```
2. **Mismatch guardrails**
   ```python
   filtered = high_score[
       (high_score["MM0"] >= 1) &
       (high_score["MM1"] == 0) &
       (high_score["MM2"] == 0)
   ]
   ```
3. **Adaptive MM0 tolerance**
   ```python
   for gene, group in filtered.groupby("Gene"):
       floor = group["MM0"].min()
       keep = group[group["MM0"] <= floor + mm0_tolerance]
   ```
4. **Rank & cap per gene**
   ```python
   top_guides = (
       keep.sort_values(["Gene", "Score"], ascending=[True, False])
           .groupby("Gene")
           .head(top_n)
   )
   ```

### Invalid Guide Detection
The workflow flags MM0 = 0 guides before filtering:
```python
invalid_guides = df[df["MM0"] == 0]
if not invalid_guides.empty:
    logger.warning("⚠️  INVALID GUIDES DETECTED (MM0=0)")
```
This surfaces incomplete off-target searches or reference mismatches so you can re-run affected steps.

### MM0 Location Audit
When `validate_mm0_locations` is `true`, a secondary pass classifies perfect matches:
```
SUMMARY OF MM0 LOCATIONS
Total guides analyzed: 110
Matches only in SAME gene: 95 (86.4%)
Matches in DIFFERENT genes: 15 (13.6%)
```
Use this report to prioritize manual review of guides with cross-gene perfect matches.

---

## Validation & Quality Control

### Guarantees for `final_guides.csv`
- Score ≥ configured `min_guide_score` (default 0.80)
- MM0 ≥ 1 (each guide perfectly matches at least its intended target)
- MM1 = 0 and MM2 = 0
- MM0 constrained to `[min_MM0, min_MM0 + mm0_tolerance]`

### Quick Validation Commands
```bash
# Confirm score threshold
awk -F',' 'NR>1 && $3 < 0.80' output/final_guides.csv | wc -l

# Ensure no invalid guides
awk -F',' 'NR>1 && $5 == 0' output/final_guides.csv | wc -l

# Check MM1/MM2 remain zero
awk -F',' 'NR>1 && ($6 > 0 || $7 > 0)' output/final_guides.csv | wc -l

# Guide counts per gene
cut -d',' -f1 output/final_guides.csv | tail -n +2 | sort | uniq -c

# Score distribution snapshot
awk -F',' 'NR>1 {print $3}' output/final_guides.csv | sort -n | head -10
```

---

## Troubleshooting

### Workflow stops early or logs errors
- Inspect `output/workflow.log` for the failing step
- Re-run diagnostics: `./preflight_check.sh`
- Resume from the last successful stage with `--resume-from`

### "Module not found" / TensorFlow complaints
- Occurs when bypassing the launcher — re-run via `scripts/04_run_workflow.sh ...`

### "Gene has no guides with score ≥ 0.80"
- Lower the threshold: `min_guide_score: 0.70`
- Confirm off-target search finished: `wc -l output/offtarget/results.csv`

### "Invalid guides detected (MM0=0)"
- Indicates incomplete or corrupt off-target counts
- Re-run off-target stage or check SLURM job completion

### "No guides found matching adaptive criteria"
1. Lower `min_guide_score`
2. Increase `mm0_tolerance`
3. As a last resort, relax `mm1_threshold` / `mm2_threshold`

### Need more visibility
```bash
scripts/04_run_workflow.sh targets.txt --verbose
less output/workflow.log
```

---

## Enhancements (2025-09-30)

### Summary of Improvements
1. **Embedded TIGER model** – Workflow is fully self-contained
2. **MM0 ≥ 1 enforcement** – Invalid guides are detected and filtered out
3. **Score-first filtering** – High TIGER scores prioritized before MM checks
4. **MM0 tolerance control** – Balance specificity with guide availability
5. **MM0 location validation** – Optional audit for perfect-match placements

### TIGER Integration Details
```
lib/
├── tiger_core/          # Local TIGER implementation
├── tiger/predictor.py   # Updated to call tiger_core
models/
└── tiger_model/         # SavedModel + calibration assets
scripts/04_run_workflow.sh    # Single-line launcher (wraps the environment)
run_with_tiger_env.sh    # Environment wrapper (still available for advanced chaining)
```
Workflow commands now rely solely on these bundled assets—no external TIGER checkout required.

### Filtering & Validation Upgrades
- Filtering pipeline logs the population after each step for transparency
- `mm0_tolerance` exposes flexible specificity controls
- MM0 location validation highlights cross-gene perfect matches for review

---

## Best Practices
- Use canonical transcripts (default Ensembl behavior already enforces this)
- Keep filtering strict (MM1 = 0, MM2 = 0) unless you understand the risk
- Prioritize guides with TIGER score > 0.70; > 0.80 is ideal for production
- Validate computational picks experimentally before large-scale usage
- Preserve intermediate files and logs for reproducibility

---

## Developing & Extending

### Where to Modify
- New filter logic → `workflows/master.py::_step_filter`
- TIGER scoring tweaks → `lib/tiger/predictor.py`
- Sequence download changes → `lib/download/ensembl.py`
- Off-target performance → `lib/offtarget/search.c`

### Test Changes Quickly
```bash
# Single-gene test run
cat > test.txt <<'EOF'
Nanog
EOF
scripts/04_run_workflow.sh test.txt --output-dir test_out --verbose
cat test_out/final_guides.csv
```

---

## References & Support
- **Logs & diagnostics**: `output/workflow.log`, `./preflight_check.sh`
- **Support commands**: `--help`, `--dry-run`, `--resume-from`, `--verbose`
- **Scientific references**:
  - TIGER — Wesley et al., *Nat. Biotechnol.* (2024)
  - Cas13 — Abudayyeh et al., *Science* (2016)
  - Ensembl REST API — https://rest.ensembl.org
- **License**: MIT (unless overridden by project policy)
- **Questions?** Check the log first, then share the failure context along with `workflow.log` and `config.yaml`

---

**Ready to design guides! 🧬**
