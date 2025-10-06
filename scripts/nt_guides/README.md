# Non-Targeting Guide Design Tools

This directory contains scripts for generating and validating non-targeting (NT) control guides for Cas13 screens.

## Overview

Non-targeting guides are essential negative controls that should not perturb any transcripts in the target organism. These tools leverage TIGER's off-target detection algorithm to ensure candidate sequences have zero complementarity to the transcriptome.

## Scripts

### `generate_nt_candidates.py`

Generates random 23-nucleotide sequences with quality filters to create NT guide candidates.

**Usage:**
```bash
python3 scripts/nt_guides/generate_nt_candidates.py [num_candidates]
```

**Features:**
- Generates sequences with balanced GC content (40-60%)
- Filters out homopolymer runs (e.g., AAAA, GGGG)
- Filters out dinucleotide repeats (e.g., ATATAT)
- Ensures sequence uniqueness
- Reproducible with fixed random seed

**Example:**
```bash
# Generate 30 candidates
python3 scripts/nt_guides/generate_nt_candidates.py 30

# Generate candidates and save to file
python3 scripts/nt_guides/generate_nt_candidates.py 50 2>/dev/null | cut -f1 > my_candidates.txt
```

**Output:**
Each line contains a sequence and its GC content:
```
AAGCCCAATAAACCACTCTGACT	# GC=43.5%
GGCCGAATAGGGATATAGGCAAC	# GC=52.2%
...
```

### `test_nt_candidates.py`

Validates NT candidate sequences by screening them against the mouse transcriptome using TIGER's off-target search.

**Usage:**
```bash
python3 scripts/nt_guides/test_nt_candidates.py
```

**Configuration:**
Edit the script to change the input file (default: `examples/targets/NT_candidates.txt`):
```python
candidates_file = ROOT_DIR / "examples/targets/NT_candidates.txt"
```

**Features:**
- Runs comprehensive off-target analysis (MM0, MM1, MM2)
- Filters for perfect candidates (zero off-targets at all mismatch levels)
- Generates detailed CSV reports
- Provides summary statistics

**Output Files:**
- `runs/nt_validation/nt_candidates_offtarget.csv` – Complete results with off-target counts
- `runs/nt_validation/perfect_nt_candidates.csv` – Filtered list of perfect NT candidates
- Console output shows top 7 candidates ready to use

**Example Output:**
```
OFF-TARGET ANALYSIS RESULTS
============================================================
Total candidates: 30
Candidates with MM0=0: 30
Candidates with MM1=0: 30
Candidates with MM2=0: 30
Perfect candidates (MM0=MM1=MM2=0): 30

✅ SUCCESS: Found 30 perfect NT candidates!

Top 7 candidates to add to NT.txt:
  AAGCCCAATAAACCACTCTGACT
  GGCCGAATAGGGATATAGGCAAC
  ...
```

### `test_single_nt.py`

Quick validation script for testing a small number of sequences (useful for debugging).

**Usage:**
```bash
python3 scripts/nt_guides/test_single_nt.py
```

**Features:**
- Tests 3 hardcoded sequences
- Fast runtime (~45 seconds)
- Useful for verifying the off-target search setup

## Workflow Example

Complete workflow for designing 10 NT guides:

```bash
# 1. Generate candidates (create more than needed)
python3 scripts/nt_guides/generate_nt_candidates.py 30 2>/dev/null | \
  cut -f1 > examples/targets/my_nt_candidates.txt

# 2. Validate candidates
# First, edit test_nt_candidates.py to point to your file:
# candidates_file = ROOT_DIR / "examples/targets/my_nt_candidates.txt"

python3 scripts/nt_guides/test_nt_candidates.py

# 3. Review perfect candidates
head -10 runs/nt_validation/perfect_nt_candidates.csv

# 4. Add selected sequences to your NT guide file
# Select 10 sequences from perfect_nt_candidates.csv
cat runs/nt_validation/perfect_nt_candidates.csv | \
  awk -F',' 'NR>1 && NR<=11 {print $2}' >> examples/targets/NT.txt
```

## Species Configuration

### Mouse (default)
```python
reference_path = ROOT_DIR / "resources/reference/gencode.vM37.transcripts.uc.joined"
```

### Human
To validate against human transcriptome, edit the scripts:
```python
reference_path = ROOT_DIR / "resources/reference/gencode.v47.transcripts.fa"
```

## Performance Notes

- **Runtime**: ~15 seconds per sequence on typical HPC nodes
- **Batch size**: Test 20-30 candidates at once for best efficiency
- **Success rate**: With proper filtering, typically >80% of candidates pass validation

## Quality Criteria

A perfect NT guide candidate must have:
- ✅ **MM0 = 0**: No perfect matches in the transcriptome
- ✅ **MM1 = 0**: No 1-mismatch hits in the transcriptome
- ✅ **MM2 = 0**: No 2-mismatch hits in the transcriptome
- ✅ **GC content**: 40-60%
- ✅ **No repeats**: No homopolymer or dinucleotide repeats ≥4bp

## Pre-validated Guides

The repository includes 10 pre-validated mouse NT guides in `examples/targets/NT.txt`:
- All confirmed zero off-targets (MM0=MM1=MM2=0)
- Validated against gencode.vM37 mouse transcriptome
- Ready to use in your screens

## Troubleshooting

**Issue**: Script can't find reference transcriptome
```
Solution: Verify resources/reference/gencode.vM37.transcripts.uc.joined exists
Run: ls -lh resources/reference/
```

**Issue**: Off-target search is slow
```
Solution: This is expected - each sequence takes ~15 seconds
For faster results, use test_single_nt.py with fewer sequences first
```

**Issue**: No perfect candidates found
```
Solution: Generate more candidates (try 50-100)
python3 scripts/nt_guides/generate_nt_candidates.py 100 2>/dev/null | cut -f1 > new_batch.txt
```

## Advanced Usage

### Custom GC content range
Edit `generate_nt_candidates.py`:
```python
seq = generate_candidate(length=23, gc_min=45, gc_max=55)  # Stricter GC range
```

### Custom repeat filtering
Edit `generate_nt_candidates.py`:
```python
if has_repeats(seq, max_repeat=3):  # Stricter: no AAA/GGG/etc.
```

### Process large batches
For >100 candidates, consider chunking:
```bash
python3 scripts/nt_guides/generate_nt_candidates.py 200 2>/dev/null | \
  split -l 30 - batch_
# Then test each batch separately
```

## References

- TIGER off-target search uses C-based binary for performance
- Binary location: `bin/offtarget_search`
- Reference transcriptomes: `resources/reference/`
- Configuration: `configs/default.yaml`
