#!/bin/bash
#SBATCH --account=nslab
#SBATCH --time=16:00:00
#SBATCH --mem=200G
#SBATCH --cpus-per-task=16
#SBATCH --output=runs/%x/slurm_%j.out
#SBATCH --error=runs/%x/slurm_%j.err

# TIGER Workflow SLURM Submission Script
# =======================================
# Usage:
#   sbatch --job-name=my_run scripts/submit_workflow.sh targets.txt --species mouse
#   sbatch --job-name=test_run scripts/submit_workflow.sh examples/targets/sofia_targets.txt --species mouse --top-n 10

set -euo pipefail

echo "=========================================="
echo "TIGER Workflow - SLURM Job"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $SLURMD_NODENAME"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "Memory: $SLURM_MEM_PER_NODE MB"
echo "Start Time: $(date)"
echo "=========================================="
echo

# Get root directory
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

# Create output directory based on job name
OUTPUT_DIR="runs/${SLURM_JOB_NAME}"
mkdir -p "$OUTPUT_DIR"

echo "Root Directory: $ROOT_DIR"
echo "Output Directory: $OUTPUT_DIR"
echo "Arguments: $@"
echo

# Run workflow with environment wrapper
scripts/04_run_workflow.sh "$@" --output-dir "$OUTPUT_DIR" --threads "$SLURM_CPUS_PER_TASK"

EXIT_CODE=$?

echo
echo "=========================================="
echo "Job Completed"
echo "=========================================="
echo "Exit Code: $EXIT_CODE"
echo "End Time: $(date)"
echo "Output Directory: $OUTPUT_DIR"
echo "=========================================="

exit $EXIT_CODE
