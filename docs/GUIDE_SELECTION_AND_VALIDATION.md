# Guide Selection and Validation in TIGER

This document explains how TIGER finds final guides, validates them, and tracks transcript-level matches including isoform information.

## Table of Contents

1. [Workflow Overview](#workflow-overview)
2. [Understanding Off-Target Counts](#understanding-off-target-counts)
3. [MM0 Location Validation](#mm0-location-validation)
4. [Interpreting Results](#interpreting-results)
5. [Enabling Transcript-Level Analysis](#enabling-transcript-level-analysis)

---

## Workflow Overview

TIGER uses a 4-step pipeline to design and validate Cas13 guides:

### Step 1: Download Sequences
- Downloads CDS sequences from Ensembl for target genes
- Resolves gene symbols to Ensembl IDs
- Output: `runs/<name>/sequences/all_targets.fasta`

### Step 2: TIGER Scoring
- Generates all possible 23nt guide sequences from CDS
- Uses ML model to predict guide efficacy
- Output: `runs/<name>/tiger/guides.csv`
  - Columns: `Gene`, `Position`, `Sequence`, `Score`, `Target`
  - Contains hundreds to thousands of candidates per gene

### Step 3: Off-Target Search
- Searches each guide against entire transcriptome
- Uses fast C binary for performance
- Counts matches at 0-5 mismatches (MM0, MM1, MM2, MM3, MM4, MM5)
- Output: `runs/<name>/offtarget/results.csv`
  - Same columns as TIGER output + `MM0`, `MM1`, `MM2`, `MM3`, `MM4`, `MM5`

### Step 4: Filtering and Ranking
- Filters by TIGER score (default: ≥0.80)
- Filters by off-target counts (default: MM1≤0, MM2≤0)
- Applies adaptive MM0 filtering per gene
- Selects top N guides per gene (default: 10)
- Output: `runs/<name>/final_guides.csv`

---

## Understanding Off-Target Counts

### What MM0/MM1/MM2 Represent

The off-target search counts how many times a guide sequence matches the transcriptome at different mismatch levels:

- **MM0**: Perfect matches (0 mismatches)
- **MM1**: Matches with 1 mismatch
- **MM2**: Matches with 2 mismatches
- **MM3-MM5**: Matches with 3-5 mismatches

### Example Output
```csv
Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5
Ccnd1,CCACTTCGCAGCACAGGAGCTGG,0,0,0,0,0,0
Pcsk9,ACCGCAGCCACGCAGAGCAGTGG,5,12,45,123,456,1234
```

### Important Limitations

**⚠️ The C-based off-target search only counts matches - it does NOT record:**
- Which transcripts the matches are in
- Which genes the matches belong to
- Whether MM0 > 1 is due to multiple isoforms of the same gene

This means:
- **MM0 = 3** could mean:
  - ✅ 3 isoforms of the target gene (GOOD - expected)
  - ⚠️ 1 target gene + 2 off-target genes (CONCERNING)
- **You cannot distinguish these cases from the off-target counts alone!**

### Adaptive MM0 Filtering

The workflow uses "adaptive MM0" filtering to handle isoforms intelligently:

```yaml
filtering:
  adaptive_mm0: true
  mm0_tolerance: 3  # Allow guides with MM0 up to (min_MM0 + 3)
```

**How it works:**
1. For each gene, find the minimum MM0 among all guides
2. Keep only guides with MM0 ≤ (min_MM0 + tolerance)
3. This ensures all guides for a gene have similar isoform coverage

**Example:**
```
Gene Actb guides:
- Guide A: MM0=2 (matches 2 isoforms)
- Guide B: MM0=2 (matches 2 isoforms)
- Guide C: MM0=5 (matches 2 target + 3 off-target)

With mm0_tolerance=3:
- min_MM0 = 2
- threshold = 2 + 3 = 5
- All guides pass (but Guide C might be problematic!)
```

**To be stricter:**
```yaml
mm0_tolerance: 0  # Only allow guides with minimum MM0
```

---

## MM0 Location Validation

### The Validation Tool

TIGER includes a **powerful validation script** that analyzes exactly which transcripts each guide matches:

**Location:** `tiger_guides_pkg/src/tiger_guides/tiger/validation.py`

### What It Does

The validation script:
1. ✅ Searches guides against the full FASTA transcriptome
2. ✅ Identifies **exact transcript IDs** for all MM0 matches
3. ✅ Extracts **gene symbols** from transcript headers
4. ✅ Categorizes matches as:
   - **SAME_GENE_ONLY**: All MM0 matches are different isoforms of target gene
   - **DIFFERENT_GENES**: Some MM0 matches are in off-target genes
5. ✅ Lists specific transcript names (e.g., "Actb-201", "Actb-202")
6. ✅ Counts occurrences per transcript

### Output Format

The validation creates a detailed CSV with these columns:

```csv
Gene,Target Sequence,Guide Score,MM0,Total Matches,Category,Matching Transcripts,Num Transcripts,Same Gene Occurrences,Other Gene Transcripts,Other Gene Count,Other Gene Occurrences
Actb,GCCGGTGCTGTGATCTCTATGAG,0.95,3,3,SAME_GENE_ONLY,"Actb-201, Actb-202, Actb-203",3,3,"",0,0
Pcsk9,ACCGCAGCCACGCAGAGCAGTGG,0.90,5,5,DIFFERENT_GENES,"Pcsk9-201, Pcsk9-202",2,2,"Ldlr-201, Apob-203, Srebf2-201",3,3
```

### Understanding the Results

**SAME_GENE_ONLY (Ideal)**
- All MM0 matches are in the target gene
- Different isoforms of the same gene are fine!
- Example: `Actb` guide matches `Actb-201`, `Actb-202`, `Actb-203`

**DIFFERENT_GENES (Concerning)**
- Some MM0 matches are in other genes
- Potential off-target effects
- Example: `Pcsk9` guide also matches `Ldlr`, `Apob`, `Srebf2`

### Key Columns Explained

| Column | Meaning |
|--------|---------|
| **MM0** | Total perfect matches (from off-target search) |
| **Total Matches** | Sum of all occurrences across all transcripts |
| **Category** | SAME_GENE_ONLY or DIFFERENT_GENES |
| **Matching Transcripts** | Target gene isoforms matched (comma-separated) |
| **Num Transcripts** | Number of target gene isoforms |
| **Same Gene Occurrences** | Total hits within target gene |
| **Other Gene Transcripts** | Off-target gene transcripts (if any) |
| **Other Gene Count** | Number of off-target genes |
| **Other Gene Occurrences** | Total hits in off-target genes |

---

## Interpreting Results

### Case Study 1: Perfect Guide

```csv
Gene: Actb
MM0: 3
Category: SAME_GENE_ONLY
Matching Transcripts: Actb-201, Actb-202, Actb-203
Other Gene Count: 0
```

**Interpretation:**
- ✅ Guide matches 3 isoforms of Actb
- ✅ No off-target genes
- ✅ Safe to use

### Case Study 2: Isoform-Rich Gene

```csv
Gene: Ttn
MM0: 15
Category: SAME_GENE_ONLY
Matching Transcripts: Ttn-201, Ttn-202, ..., Ttn-215
Other Gene Count: 0
```

**Interpretation:**
- ✅ Gene has 15 isoforms
- ✅ Guide targets all/most isoforms (comprehensive knockdown)
- ✅ No off-target genes
- ✅ Safe to use

### Case Study 3: Problematic Off-Target

```csv
Gene: Pcsk9
MM0: 5
Category: DIFFERENT_GENES
Matching Transcripts: Pcsk9-201, Pcsk9-202
Other Gene Transcripts: Ldlr-201, Apob-203, Srebf2-201
Other Gene Count: 3
Other Gene Occurrences: 3
```

**Interpretation:**
- ⚠️ Guide matches 2 isoforms of Pcsk9 (good)
- ⚠️ BUT also matches 3 other genes
- ⚠️ Could cause off-target knockdown
- ❌ Consider choosing a different guide

### Case Study 4: Multiple Matches Per Transcript

```csv
Gene: Rps3
MM0: 8
Category: SAME_GENE_ONLY
Matching Transcripts: Rps3-201, Rps3-202
Same Gene Occurrences: 8
```

**Interpretation:**
- Guide appears 8 times across 2 isoforms
- Likely due to repeated sequence motifs
- Still safe (same gene), but unusual
- Consider if this affects guide design

---

## Enabling Transcript-Level Analysis

### Method 1: Via Configuration (Recommended)

Enable MM0 location validation in your config file:

```yaml
# configs/my_config.yaml
output:
  validate_mm0_locations: true  # Enable transcript-level analysis
```

Then run the workflow:
```bash
scripts/04_run_workflow.sh targets.txt --species mouse --config configs/my_config.yaml
```

**Note:** Currently this flag exists in the config but the validation step is **not automatically integrated** into the workflow runner. See Method 2 for manual usage.

### Method 2: Manual Analysis (Current Method)

After running the workflow, manually run the validation script:

```python
from tiger_guides.tiger.validation import validate_final_guides

# Analyze final guides
validate_final_guides(
    guides_csv="runs/latest/final_guides.csv",
    transcriptome_file="resources/reference/gencode.vM37.transcripts.uc.joined",
    output_file="runs/latest/mm0_location_analysis.csv"
)
```

Or use the command-line script:

```bash
cd tiger_guides_pkg/src/tiger_guides/tiger
python3 validation.py
```

**You need to edit the script to point to your files:**
```python
# In validation.py main() function:
guides_csv = "path/to/your/final_guides.csv"
transcriptome_file = "path/to/gencode.vM37.transcripts.fa"
output_file = "path/to/mm0_analysis.csv"
```

### Method 3: Integrate into Workflow (Advanced)

To automatically run MM0 validation after filtering, modify the workflow runner:

**File:** `tiger_guides_pkg/src/tiger_guides/workflow/runner.py`

Add after the filtering step (`_step_filter` method):

```python
def _step_filter(self, offtarget_output: Path) -> Optional[Path]:
    # ... existing filtering code ...

    # Add MM0 location validation if enabled
    if self.config.get("output", {}).get("validate_mm0_locations", False):
        self.logger.info("\n" + "=" * 60)
        self.logger.info("OPTIONAL: MM0 Location Analysis")
        self.logger.info("=" * 60)

        from ..tiger.validation import validate_final_guides

        # Get reference transcriptome
        ref_path = self.config["offtarget"]["reference_transcriptome"]
        if not Path(ref_path).is_absolute():
            ref_path = (self.root / ref_path).resolve()

        # Run validation
        mm0_output = self.output_dir / "mm0_location_analysis.csv"
        validate_final_guides(
            guides_csv=final_csv,
            transcriptome_file=str(ref_path),
            output_file=str(mm0_output),
            logger=self.logger
        )

    return final_csv
```

---

## Summary

### Quick Reference

| Question | Answer |
|----------|--------|
| **Does off-target search track which transcripts match?** | No, it only counts matches |
| **Can MM0 > 1 be due to isoforms?** | Yes! This is very common |
| **How do I know if MM0 matches are same gene or off-target?** | Use the validation script |
| **Is the validation automatic?** | No (currently), run manually or integrate |
| **What file has transcript details?** | `mm0_location_analysis.csv` (from validation) |
| **Should I worry about MM0=5?** | Check validation - could be 5 isoforms (OK) or off-targets (bad) |

### Best Practices

1. **Always run MM0 location validation** for final guide sets
2. **Prioritize guides** with `Category=SAME_GENE_ONLY`
3. **Investigate guides** with `Other Gene Count > 0`
4. **Consider the biology**: Some genes naturally have many isoforms
5. **Use adaptive_mm0** with appropriate tolerance for isoform-rich genes
6. **Set mm0_tolerance=0** if you want the strictest filtering

### Common Scenarios

**High MM0 count = Multiple isoforms (Good)**
```
Gene: Ttn
MM0: 20
Category: SAME_GENE_ONLY
→ This gene has 20+ isoforms, guide targets all of them
```

**High MM0 count = Off-target genes (Bad)**
```
Gene: GeneX
MM0: 20
Category: DIFFERENT_GENES
Other Gene Count: 18
→ Guide matches 18 other genes! Choose different guide
```

**You cannot tell the difference without running the validation script!**

---

## Technical Details

### Transcriptome Header Format

The validation script parses FASTA headers in this format:

```
>ENSMUST00000193812.2|ENSMUSG00000102693.2|...|Actb-201|Actb|...
 ^transcript_id      ^gene_id              ^name    ^symbol
```

- **Transcript ID**: Ensembl transcript identifier
- **Transcript Name**: e.g., "Actb-201" (gene symbol + isoform number)
- **Gene Symbol**: e.g., "Actb"

### Performance Notes

- **Off-target search**: ~15 seconds per sequence (C binary, very fast)
- **MM0 validation**: ~1-2 seconds per guide (Python, slower)
- **Recommendation**: Run off-target search on all guides, then validation on final set only

### Limitations

1. **Validation requires FASTA format** (not the concatenated `.joined` format)
2. **Header parsing is format-specific** (assumes Gencode/Ensembl headers)
3. **No MM1/MM2 location tracking** (only MM0/perfect matches)
4. **Memory intensive** for large transcriptomes (loads entire reference)

---

## Frequently Asked Questions

### Q: Why doesn't the workflow automatically show transcript matches?

**A:** Performance and modularity. The C-based off-target search is optimized for speed (counts only). The Python validation is slower but provides detailed information. Running validation on all candidates would be too slow, so it's designed for final guide sets.

### Q: Can I get transcript info for MM1 and MM2 matches?

**A:** Not currently. The validation script only analyzes perfect matches (MM0). For MM1/MM2, you'd need to modify the script to search with mismatches allowed.

### Q: What if my MM0 validation shows DIFFERENT_GENES?

**A:** Options:
1. Choose a different guide for that gene (from `final_guides.csv`)
2. Lower the `min_guide_score` to get more candidates
3. Manually inspect if the off-target genes are biologically relevant
4. Accept the off-target if it's acceptable for your experiment

### Q: How do I cite this in my paper?

**Example methods section:**
> Guide RNAs were designed using the TIGER workflow with off-target analysis. Final guides were validated to ensure MM0 perfect matches occurred only within target gene isoforms and not in off-target genes.

---

For more information, see:
- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - Complete workflow documentation
- [README.md](../README.md) - Quick start guide
- Source code: `tiger_guides_pkg/src/tiger_guides/tiger/validation.py`
