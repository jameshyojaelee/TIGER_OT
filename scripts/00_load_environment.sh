#!/bin/bash
# 00_load_environment.sh -- configure modules and PYTHONPATH for TIGER
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

module purge 2>/dev/null || true

USE_GPU=${TIGER_USE_GPU:-0}
TF_MODULE=${TIGER_TF_MODULE:-TensorFlow/2.15.1-base}
if [ "$USE_GPU" = "1" ]; then
  TF_MODULE=${TIGER_TF_GPU_MODULE:-TensorFlow/2.15.1}
fi

module load "${TF_MODULE}" 2>/dev/null || true

export PYTHONPATH="${ROOT_DIR}/vendor/venv_packages:${ROOT_DIR}/src:${PYTHONPATH:-}"
export TF_ENABLE_ONEDNN_OPTS=0

if [ "$USE_GPU" = "1" ]; then
  unset CUDA_VISIBLE_DEVICES
  export TF_FORCE_GPU_ALLOW_GROWTH=1
else
  export CUDA_VISIBLE_DEVICES=""
  export TF_CPP_MIN_LOG_LEVEL=${TF_CPP_MIN_LOG_LEVEL:-3}
fi

exec "$@"
