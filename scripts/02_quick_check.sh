#!/bin/bash
# 02_quick_check.sh -- fast post-setup sanity check
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"
WRAPPER="${ROOT_DIR}/scripts/00_load_environment.sh"
if [ -x "$WRAPPER" ]; then
  PY_CMD=("$WRAPPER" python3)
else
  PY_CMD=(python3)
fi

cat <<'HDR'
============================================================
Cas13 TIGER Workflow · Step 02/04 — Quick Setup Check
Runs lightweight checks after scripts/01_setup_workspace.sh.
============================================================
HDR

status_ok=true

if [ -x "bin/offtarget_search" ]; then
  echo "✅ C binary present: bin/offtarget_search"
else
  echo "❌ Missing C binary. Run: make"
  status_ok=false
fi

if "${PY_CMD[@]}" - <<'PY'; then
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
from utils.logger import setup_logger  # noqa: F401
from utils.config import load_config  # noqa: F401
from download.ensembl import EnsemblDownloader  # noqa: F401
print('✅ Python module import test passed')
PY
  :
else
  echo "❌ Python import test failed (see traceback above)"
  status_ok=false
fi

MODEL_DIR="resources/models/tiger_model"
if [ -d "$MODEL_DIR" ] || [ -L "$MODEL_DIR" ]; then
  echo "✅ Model directory found: $MODEL_DIR"
else
  echo "⚠️  Model assets missing. Link your TIGER model into $MODEL_DIR"
  status_ok=false
fi

declare -A REF_PATHS
REF_PATHS[mouse]="resources/reference/gencode.vM37.transcripts.uc.joined"
REF_PATHS[human]="resources/reference/gencode.v47.transcripts.fa"

for species in "${!REF_PATHS[@]}"; do
  ref_path="${REF_PATHS[$species]}"
  label="${species^}"
  if [ -f "$ref_path" ]; then
    echo "✅ $label transcriptome present: $ref_path"
  elif [ -L "$ref_path" ]; then
    target=$(readlink "$ref_path")
    if [ -e "$ref_path" ]; then
      echo "✅ $label transcriptome symlink resolves: $ref_path -> $target"
    else
      echo "⚠️  $label transcriptome symlink broken: $ref_path -> $target"
      status_ok=false
    fi
  else
    echo "⚠️  $label transcriptome missing at $ref_path"
    status_ok=false
  fi
done

if [ -x "$WRAPPER" ]; then
  if "$WRAPPER" python3 - <<'PY' 2>/dev/null; then
import tensorflow as tf
print('TensorFlow:', tf.__version__)
PY
    echo "✅ TensorFlow available via scripts/00_load_environment.sh"
  else
    echo "⚠️  TensorFlow not available via scripts/00_load_environment.sh"
    status_ok=false
  fi
else
  echo "⚠️  Environment wrapper missing (scripts/00_load_environment.sh)"
  status_ok=false
fi

if [ -f "targets.txt" ]; then
  n_targets=$(grep -v '^#' targets.txt | grep -v '^$' | wc -l)
  echo "✅ targets.txt present with $n_targets entries"
else
  echo "ℹ️  targets.txt not found; copy examples/targets/example_targets.txt to get started"
fi

echo ""
if [ "$status_ok" = true ]; then
  cat <<'DONE'
Quick check passed.
Next: scripts/03_preflight_check.sh for the full diagnostics suite.
DONE
  exit 0
else
  cat <<'WARN'
Quick check finished with warnings. Resolve the issues above before
continuing to scripts/03_preflight_check.sh.
WARN
  exit 1
fi
