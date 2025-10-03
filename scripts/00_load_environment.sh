#!/bin/bash
################################################################################
# TIGER Environment Wrapper
# 
# This script sets up the correct Python environment for TIGER
################################################################################

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Purge conflicting modules
module purge 2>/dev/null

# Decide whether to run on GPU or CPU only
USE_GPU=${TIGER_USE_GPU:-0}
TF_MODULE=${TIGER_TF_MODULE:-TensorFlow/2.15.1-base}
if [ "$USE_GPU" = "1" ]; then
  TF_MODULE=${TIGER_TF_GPU_MODULE:-TensorFlow/2.15.1}
fi

# Load TensorFlow environment
module load "${TF_MODULE}" 2>/dev/null

# Add local venv_packages to PYTHONPATH (for pyyaml, biopython, requests)
export PYTHONPATH="${SCRIPT_DIR}/venv_packages:$PYTHONPATH"

# Disable oneDNN custom operations (reduces warnings)
export TF_ENABLE_ONEDNN_OPTS=0

if [ "$USE_GPU" = "1" ]; then
  # Allow TensorFlow to see available GPUs
  unset CUDA_VISIBLE_DEVICES
  export TF_FORCE_GPU_ALLOW_GROWTH=1
else
  # Force CPU execution and quiet redundant CUDA plugin warnings
  export CUDA_VISIBLE_DEVICES=""
  export TF_CPP_MIN_LOG_LEVEL=${TF_CPP_MIN_LOG_LEVEL:-3}
fi

# Run the command passed as arguments
exec "$@"
