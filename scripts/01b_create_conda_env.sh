#!/bin/bash
# 01b_create_conda_env.sh -- optional conda-based environment setup
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

cat <<'HDR'
============================================================
Cas13 TIGER Workflow · Optional Conda Environment (Step 01b)
Use this script if you prefer an isolated conda env instead of modules.
============================================================
HDR

if ! command -v conda >/dev/null 2>&1; then
  echo "Conda not found on PATH. Attempting to load an Anaconda module..."
  module purge || true
  module load Anaconda3 2>/dev/null || module load anaconda3 2>/dev/null || {
    echo "❌ Failed to load Anaconda module; install conda or contact an admin."
    exit 1
  }
fi

ENV_NAME=${TIGER_CONDA_ENV:-tiger_env}

if conda env list | grep -q "^${ENV_NAME} "; then
  echo "Conda environment '${ENV_NAME}' already exists."
  read -rp "Recreate it? (y/N) " reply
  if [[ $reply =~ ^[Yy]$ ]]; then
    conda env remove -n "$ENV_NAME"
  else
    echo "Keeping existing environment."
    exit 0
  fi
fi

cat <<MSG
Creating conda environment '${ENV_NAME}' with Python 3.10 and dependencies...
MSG
conda create -n "$ENV_NAME" python=3.10 -y

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

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
cat <<MSG
Conda environment '${ENV_NAME}' is ready.
Next steps:
  1. conda activate ${ENV_NAME}
  2. Run scripts/01_setup_workspace.sh (skip the pip install section if desired)
  3. Launch the workflow via scripts/04_run_workflow.sh targets.txt
MSG
