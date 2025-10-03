#!/bin/bash
################################################################################
# Setup TIGER Environment
# Creates a conda environment with all dependencies
################################################################################

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Setting up TIGER Environment"
echo "============================================================"
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Loading Anaconda module..."
    module purge
    module load Anaconda3 2>/dev/null || module load anaconda3 2>/dev/null || {
        echo "❌ Could not load Anaconda module"
        echo "Please install conda or contact your system administrator"
        exit 1
    }
fi

ENV_NAME="tiger_env"

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Environment '$ENV_NAME' already exists"
    echo "To recreate, run: conda env remove -n $ENV_NAME"
    echo ""
    read -p "Use existing environment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        conda env remove -n $ENV_NAME
    else
        echo "Using existing environment"
        exit 0
    fi
fi

# Create conda environment
echo "Creating conda environment: $ENV_NAME"
conda create -n $ENV_NAME python=3.10 -y

# Activate environment
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $ENV_NAME

# Install dependencies
echo ""
echo "Installing dependencies..."
conda install -c conda-forge \
    tensorflow=2.15 \
    biopython \
    pyyaml \
    pandas \
    numpy \
    requests \
    tqdm \
    -y

echo ""
echo "============================================================"
echo "Environment Setup Complete!"
echo "============================================================"
echo ""
echo "To use the TIGER workflow:"
echo ""
echo "  conda activate $ENV_NAME"
echo "  python3 run_tiger.py targets.txt"
echo ""
echo "Or use the wrapper script:"
echo ""
echo "  ./run_with_conda.sh python3 run_tiger.py targets.txt"
echo ""
echo "============================================================"
