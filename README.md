#!/usr/bin/env python3
"""
Cas13 Guide Design - Master Workflow
=====================================
Standalone, optimized pipeline for Cas13 guide RNA design.

Usage:
    ./run_tiger_workflow.sh targets.txt [options]
    
Examples:
    ./run_tiger_workflow.sh targets.txt
    ./run_tiger_workflow.sh targets.txt --top-n 5
    ./run_tiger_workflow.sh targets.txt --config custom_config.yaml
"""

import sys
import argparse
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from workflows.master import Cas13WorkflowRunner
from utils.logger import setup_logger
from utils.config import load_config

def main():
    parser = argparse.ArgumentParser(
        description="Cas13 Guide Design - Complete Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  ./run_tiger_workflow.sh targets.txt
  
  # Advanced options
  ./run_tiger_workflow.sh targets.txt --top-n 5 --skip-download
  ./run_tiger_workflow.sh targets.txt --config custom.yaml --dry-run
  
  # Resume from specific step
  ./run_tiger_workflow.sh targets.txt --resume-from offtarget
        """
    )
    
    # Required arguments
    parser.add_argument(
        'targets',
        type=str,
        help='Path to targets.txt file (gene names, one per line)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='output',
        help='Output directory (default: output/)'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config.yaml',
        help='Configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top guides per gene (default: 10)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview workflow without executing'
    )
    
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip FASTA download if files exist'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation steps (faster but not recommended)'
    )
    
    parser.add_argument(
        '--resume-from',
        type=str,
        choices=['download', 'tiger', 'offtarget', 'filter'],
        help='Resume workflow from specific step'
    )
    
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Number of threads for parallel processing (default: 4)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_logger(
        'Cas13Workflow',
        verbose=args.verbose,
        log_file=f"{args.output_dir}/workflow.log"
    )
    
    # Load configuration
    main_dir = Path(__file__).parent
    config = load_config(main_dir / args.config)
    
    # Update config with command-line arguments
    config['top_n_guides'] = args.top_n
    config['output_dir'] = args.output_dir
    config['threads'] = args.threads
    
    # Initialize workflow runner
    runner = Cas13WorkflowRunner(
        targets_file=args.targets,
        config=config,
        main_dir=main_dir,
        dry_run=args.dry_run,
        logger=logger
    )
    
    # Run workflow
    try:
        success = runner.run(
            skip_download=args.skip_download,
            skip_validation=args.skip_validation,
            resume_from=args.resume_from
        )
        
        if success:
            logger.info("✅ Workflow completed successfully!")
            logger.info(f"📄 Results: {args.output_dir}/final_guides.csv")
            sys.exit(0)
        else:
            logger.error("❌ Workflow failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Workflow interrupted by user")
        logger.info("You can resume with: --resume-from <step>")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()

# Cas13 Guide Design Workflow

Complete, optimized pipeline for designing Cas13 guide RNAs using TIGER with off-target analysis.

**One command. Complete analysis. Top guides ready.**

---

## Quick Start

```bash
cd /gpfs/commons/home/jameslee/Cas13/TIGER/main

# 1. Build (one time)
make

# 2. Setup (5 minutes, one time)
./setup.sh

# 3. Create targets file
cat > targets.txt <<EOF
Nanog
Pou5f1
Sox2
Klf4
EOF

# 4. Run workflow
./run_tiger_workflow.sh targets.txt

# 5. Get results
less output/final_guides.csv
```

**That's it!** Your top 10 guides per gene are ready in `output/final_guides.csv`.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Output](#output)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)
- [Architecture](#architecture)

---

## Features

✅ **Single-command execution** - No manual steps between stages  
✅ **Fast C implementation** - 10-100x faster off-target search  
✅ **Automatic downloads** - Fetches sequences from Ensembl  
✅ **TIGER integration** - State-of-the-art ML guide prediction  
✅ **Smart filtering** - Adaptive off-target thresholds  
✅ **Resume capability** - Restart from any checkpoint  
✅ **Comprehensive logging** - Color-coded progress tracking  
✅ **SLURM support** - Parallel processing for large datasets  
✅ **Complete documentation** - This file is all you need  

---

## Installation

### Prerequisites

- Python 3.8+
- GCC compiler
- (Optional) TensorFlow for TIGER

### One-Time Setup

```bash
cd /gpfs/commons/home/jameslee/Cas13/TIGER/main

# 1. Build C binary
make

# 2. Install Python dependencies
pip install --user biopython pyyaml requests tqdm colorama

# 3. (Optional) Install TensorFlow for TIGER
pip install --user tensorflow

# 4. Link TIGER model (update path as needed)
ln -s /path/to/tiger_model models/tiger_model

# 5. Reference transcriptome
#    (Repo ships with a tiny smoke-test FASTA at reference/gencode.vM37.transcripts.uc.joined)
#    Replace that file or update config.yaml when you have the full transcriptome.

# 6. Verify setup
./CHECK_SETUP.sh
```

**Automated setup:** Just run `./setup.sh` and follow the prompts.

---

## Usage

### Basic Usage

```bash
# 1. Create targets file (one gene per line)
cat > targets.txt <<EOF
Nanog
Oct4
Sox2
EOF

# 2. Run workflow
./run_tiger_workflow.sh targets.txt

# 3. Results are in output/final_guides.csv
```

> Want GPUs? Export `TIGER_USE_GPU=1` (and if needed `TIGER_TF_GPU_MODULE` with your CUDA-enabled TensorFlow module) before launching, for example:
>
> ```bash
> TIGER_USE_GPU=1 TIGER_TF_GPU_MODULE=TensorFlow/2.15.1-gpu ./run_tiger_workflow.sh targets.txt --threads 8
> ```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `targets.txt` | Path to targets file (required) | - |
| `--output-dir, -o` | Output directory | `output` |
| `--config, -c` | Configuration file | `config.yaml` |
| `--top-n` | Number of top guides per gene | `10` |
| `--dry-run` | Preview without executing | `false` |
| `--skip-download` | Skip FASTA download | `false` |
| `--skip-validation` | Skip validation steps | `false` |
| `--resume-from` | Resume from step: `download`, `tiger`, `offtarget`, `filter` | - |
| `--threads` | Number of threads | `4` |
| `--verbose, -v` | Verbose output | `false` |

### Examples

```bash
# Preview workflow without running
./run_tiger_workflow.sh targets.txt --dry-run

# Custom output directory
./run_tiger_workflow.sh targets.txt --output-dir my_guides

# Get top 5 guides per gene (default: 10)
./run_tiger_workflow.sh targets.txt --top-n 5

# Skip download if FASTA files exist
./run_tiger_workflow.sh targets.txt --skip-download

# Resume from specific step
./run_tiger_workflow.sh targets.txt --resume-from offtarget

# Verbose logging
./run_tiger_workflow.sh targets.txt --verbose

# Use custom config
./run_tiger_workflow.sh targets.txt --config my_config.yaml

# Full help
./run_tiger_workflow.sh --help
```

### Smoke Test (Bundled)
Use the small built-in reference plus sample config to confirm everything runs end-to-end:

```bash
./run_tiger_workflow.sh test_targets.txt --config config.sample.yaml --output-dir output_smoke --skip-validation
head output_smoke/final_guides.csv
```

### Workflow Steps

The workflow automatically runs through these steps:

1. **Download** - Fetch CDS sequences from Ensembl REST API
2. **TIGER** - Predict guide scores using ML model
3. **Off-target** - Search against reference transcriptome (fast C binary)
4. **Filter** - Rank and select top guides with adaptive thresholds

**Resume points:** `download`, `tiger`, `offtarget`, `filter`

---

## Configuration

Edit `config.yaml` to customize behavior:

### Species Settings

```yaml
species: "mus_musculus"  # or "homo_sapiens"
```

### Guide Selection

```yaml
filtering:
  top_n_guides: 10          # Guides per gene
  mm1_threshold: 0          # No 1-mismatch off-targets
  mm2_threshold: 0          # No 2-mismatch off-targets
  adaptive_mm0: true        # Use adaptive MM0 filtering
```

### TIGER Settings

```yaml
tiger:
  guide_length: 23
  batch_size: 500
  context_5p: 3
  context_3p: 0
```

### Off-Target Settings

```yaml
offtarget:
  max_mismatches: 5
  chunk_size: 1500          # For SLURM parallelization
```

### SLURM Settings

```yaml
slurm:
  account: "sanjana"
  partition: "cpu"
  time: "02:00:00"
  mem: "8G"
```

---

## Output

### Final Results: `output/final_guides.csv`

| Column | Description |
|--------|-------------|
| `Gene` | Target gene name |
| `Sequence` | 23-mer guide sequence |
| `Score` | TIGER prediction score (0-1, higher is better) |
| `Position` | Position in transcript |
| `MM0` | Perfect match count in transcriptome |
| `MM1` | 1-mismatch off-target count |
| `MM2` | 2-mismatch off-target count |
| `MM3` | 3-mismatch off-target count |
| `MM4` | 4-mismatch off-target count |
| `MM5` | 5-mismatch off-target count |

### Intermediate Files

```
output/
├── sequences/
│   ├── all_targets.fasta        # Downloaded sequences
│   └── individual/              # Per-gene FASTA files
├── tiger/
│   └── guides.csv               # All predicted guides
├── offtarget/
│   └── results.csv              # Guides with off-target counts
├── final_guides.csv             # Top ranked guides
├── config.yaml                  # Run configuration
└── workflow.log                 # Detailed logs
```

### Quick Analysis

```bash
# Count guides per gene
cut -d',' -f1 output/final_guides.csv | sort | uniq -c

# View statistics
python3 -c "
import pandas as pd
df = pd.read_csv('output/final_guides.csv')
print(f'Genes: {df.Gene.nunique()}')
print(f'Total guides: {len(df)}')
print(f'Avg score: {df.Score.mean():.3f}')
print(f'Score range: {df.Score.min():.3f} - {df.Score.max():.3f}')
"
```

---

## Troubleshooting

### Common Issues

**"Binary not found"**
```bash
make clean && make
```

**"Module not found" errors**
```bash
pip install --user -r requirements.txt
```

**"Reference transcriptome not found"**
```bash
# Update path in config.yaml
offtarget:
  reference_transcriptome: "/path/to/gencode.vM37.transcripts.uc.joined"
```

**"TIGER model not found"**
```bash
# Create symlink or update config.yaml
ln -s /path/to/tiger_model models/tiger_model
```

**Memory issues**
```bash
# Reduce batch size in config.yaml
tiger:
  batch_size: 100  # Default: 500
```

**Workflow interrupted**
```bash
# Resume from last checkpoint
./run_tiger_workflow.sh targets.txt --resume-from offtarget
```

### Debug Mode

```bash
# Verbose output with full logs
./run_tiger_workflow.sh targets.txt --verbose

# Check logs
less output/workflow.log
```

### Verify Setup

```bash
./CHECK_SETUP.sh
```

This will check:
- ✅ C binary exists
- ✅ Python modules import
- ✅ TIGER model accessible
- ✅ Reference transcriptome found
- ✅ Dependencies installed

---

## Advanced Usage

### Custom Configuration

```bash
# Create custom config
cp config.yaml my_config.yaml
# Edit my_config.yaml...

# Use custom config
./run_tiger_workflow.sh targets.txt --config my_config.yaml
```

### SLURM Parallelization

For large datasets, the off-target search automatically uses SLURM array jobs:

```yaml
# In config.yaml
offtarget:
  chunk_size: 1500  # Guides per job

slurm:
  account: "sanjana"
  partition: "cpu"
  time: "02:00:00"
```

### Batch Processing Multiple Projects

```bash
# Process multiple target sets
for targets in project1.txt project2.txt project3.txt; do
    ./run_tiger_workflow.sh $targets --output-dir output_$(basename $targets .txt)
done
```

### Integration with Existing Data

```bash
# Skip download if you have FASTA already
./run_tiger_workflow.sh targets.txt \
    --skip-download \
    --config my_config.yaml
```

### Development Mode

```bash
# Dry run to preview steps
./run_tiger_workflow.sh targets.txt --dry-run

# Skip validation for faster testing
./run_tiger_workflow.sh targets.txt --skip-validation
```

---

## Architecture

### Workflow Pipeline

```
targets.txt (gene names)
         ↓
    [Download FASTA]
      Ensembl REST API
         ↓
    sequences/all_targets.fasta
         ↓
    [TIGER Prediction]
      ML model scoring
         ↓
    tiger/guides.csv
         ↓
    [Off-Target Search]
      Fast C binary
         ↓
    offtarget/results.csv
         ↓
    [Filter & Rank]
      Adaptive thresholds
         ↓
    final_guides.csv
```

### Directory Structure

```
main/
├── run_tiger.py          # Main entry point
├── config.yaml              # Configuration
├── Makefile                 # Build system
├── CHECK_SETUP.sh           # Setup verification
│
├── bin/
│   └── offtarget_search     # Compiled C binary
│
├── lib/
│   ├── download/
│   │   └── ensembl.py       # Ensembl API client
│   ├── tiger/
│   │   ├── predictor.py     # TIGER ML wrapper
│   │   └── validator.py     # Output validation
│   ├── offtarget/
│   │   ├── search.c         # C implementation
│   │   └── wrapper.py       # Python wrapper
│   └── utils/
│       ├── logger.py        # Logging system
│       ├── config.py        # Config management
│       └── slurm.py         # SLURM utilities
│
├── workflows/
│   └── master.py            # Workflow orchestrator
│
├── models/                  # TIGER model (symlink)
└── reference/               # Transcriptome (symlink)
```

### Technology Stack

| Component | Implementation | Reason |
|-----------|---------------|---------|
| **Off-target search** | C (AVX2 optimized) | 10-100x faster than Python |
| **TIGER wrapper** | Python + TensorFlow | Existing ML model |
| **Download** | Python + Requests | REST API integration |
| **Orchestration** | Python | Workflow management |
| **Configuration** | YAML | Human-readable settings |

### Performance

- **Off-target search**: ~17 KB binary, processes 1000s of guides/second
- **Batch processing**: 500 guides at a time for TIGER
- **Memory efficient**: Streaming where possible
- **Parallel ready**: SLURM array job support

---

## How It Works

### Step 1: Download Sequences

Uses Ensembl REST API to fetch CDS sequences:
- Prefers canonical transcripts
- Falls back to APPRIS principal
- Validates sequence integrity
- Saves individual + merged FASTA

### Step 2: TIGER Prediction

Generates and scores all possible guides:
- Slides 23-mer window across sequences
- Extracts context (3bp upstream)
- Runs TIGER ML model for scoring
- Outputs all guides with scores

### Step 3: Off-Target Search

Fast C implementation searches transcriptome:
- Counts mismatches (0-5 MM)
- SIMD optimization (AVX2)
- Early exit on excess mismatches
- Memory-mapped file access

### Step 4: Filter & Rank

Smart filtering and selection:
- Applies MM1/MM2 thresholds
- Adaptive MM0 filtering per gene
- Ranks by TIGER score
- Selects top N guides

---

## Example Workflow

```bash
# Create targets
cat > targets.txt <<EOF
Nanog
Pou5f1
Sox2
Klf4
Myc
EOF

# Run workflow
./run_tiger_workflow.sh targets.txt --verbose

# Output:
# INFO - Loaded 5 target genes
# INFO - Step 1: Download FASTA Sequences
# INFO - ✅ Nanog: 1089 bp
# INFO - ✅ Pou5f1: 1095 bp
# INFO - ✅ Sox2: 957 bp
# INFO - ✅ Klf4: 1404 bp
# INFO - ✅ Myc: 1281 bp
# INFO - Step 2: TIGER Guide Prediction
# INFO - ✅ Generated 3826 guides
# INFO - Step 3: Off-Target Analysis
# INFO - ✅ Completed off-target search
# INFO - Step 4: Filter and Rank Guides
# INFO - ✅ Selected top 10 guides per gene: 50 total
# INFO - ✅ Workflow completed successfully!
# INFO - 📄 Results: output/final_guides.csv

# View results
head -20 output/final_guides.csv
```

---

## Best Practices

### For Best Results

1. **Use canonical transcripts** - Default behavior via Ensembl
2. **Filter conservatively** - MM1=0, MM2=0 reduces off-targets
3. **Check TIGER scores** - Higher scores (>0.7) are better
4. **Validate experimentally** - Computational predictions are guides

### Recommended Settings

**High specificity** (fewer off-targets):
```yaml
filtering:
  mm1_threshold: 0
  mm2_threshold: 0
  adaptive_mm0: true
```

**More guides** (relaxed filtering):
```yaml
filtering:
  mm1_threshold: 1
  mm2_threshold: 5
  adaptive_mm0: false
```

### Data Management

- **Keep intermediate files** - Useful for debugging
- **Log everything** - Saves to `output/workflow.log`
- **Version configs** - Copy `config.yaml` to output directory

---

## Contributing

This is a self-contained workflow. To extend:

1. **Add new filters** - Edit `workflows/master.py::_step_filter()`
2. **Change scoring** - Modify `lib/tiger/predictor.py`
3. **Custom download** - Update `lib/download/ensembl.py`
4. **Optimize search** - Edit `lib/offtarget/search.c`

### Testing Changes

```bash
# Test with single gene
echo "Nanog" > test.txt
./run_tiger_workflow.sh test.txt --output-dir test_out --verbose

# Verify output
cat test_out/final_guides.csv
```

---

## References

- **TIGER**: Wesley et al., Nature Biotechnology (2024)
- **Cas13**: Abudayyeh et al., Science (2016)
- **Ensembl API**: https://rest.ensembl.org

---

## Support

**Setup issues?** Run `./CHECK_SETUP.sh` to diagnose

**Questions?** Check logs in `output/workflow.log`

**Need help?** See the troubleshooting section above

---

## License

MIT License (or as specified by your project)

---

**Version:** 1.0  
**Last Updated:** 2025-09-30  
**Status:** Production-ready

---

**Ready to design guides! 🧬**
