#!/bin/bash
# 02_quick_check.sh -- fast post-setup sanity check
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

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

python3 - <<'PY' || status_ok=false
import sys
from pathlib import Path
sys.path.insert(0, str(Path('lib')))
from utils.logger import setup_logger  # noqa: F401
from utils.config import load_config  # noqa: F401
from download.ensembl import EnsemblDownloader  # noqa: F401
print('✅ Python module import test passed')
PY

if [ -d "models/tiger_model" ] || [ -L "models/tiger_model" ]; then
  echo "✅ Model directory found: models/tiger_model"
else
  echo "⚠️  Model assets missing. Link your TIGER model into models/tiger_model"
  status_ok=false
fi

REF_LINK="reference/gencode.vM37.transcripts.uc.joined"
if [ -f "$REF_LINK" ]; then
  echo "✅ Reference transcriptome present: $REF_LINK"
elif [ -L "$REF_LINK" ]; then
  TARGET=$(readlink "$REF_LINK")
  if [ -e "$REF_LINK" ]; then
    echo "✅ Reference symlink resolves: $REF_LINK -> $TARGET"
  else
    echo "⚠️  Reference symlink broken: $REF_LINK -> $TARGET"
    status_ok=false
  fi
else
  echo "⚠️  Reference transcriptome missing"
  status_ok=false
fi

python3 - <<'PY' || status_ok=false
try:
    import tensorflow as tf
    print('✅ TensorFlow available:', tf.__version__)
except ImportError:
    print('⚠️  TensorFlow not installed; ensure requirements are satisfied')
    raise SystemExit(1)
PY

if [ -f "targets.txt" ]; then
  n_targets=$(grep -v '^#' targets.txt | grep -v '^$' | wc -l)
  echo "✅ targets.txt present with $n_targets entries"
else
  echo "ℹ️  targets.txt not found; copy targets.example.txt to get started"
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
