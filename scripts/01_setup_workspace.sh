#!/bin/bash
# 01_setup_workspace.sh -- build native components and install Python deps
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

cat <<'BANNER'
============================================================
Cas13 TIGER Workflow · Step 01/04 — Workspace Setup
This step builds the C helpers and installs Python requirements.
============================================================
BANNER

# Build native components
if [ -f Makefile ]; then
  echo "[1/4] Building C components (make clean && make)"
  make clean
  make
  echo "✅ Native build complete"
else
  echo "⚠️  Makefile not found in $ROOT_DIR; skipping native build"
fi

echo ""
# Install Python dependencies via pip (system or virtualenv)
echo "[2/4] Installing Python dependencies from requirements.txt"
pip install -r requirements.txt

echo ""
# Check for required model assets and hint if missing
echo "[3/4] Verifying model assets"
if [ ! -d "models/tiger_model" ]; then
  cat <<'MSG'
⚠️  Model directory missing: models/tiger_model
    Create symlinks to your TIGER model assets, for example:
      ln -s /path/to/tiger_model models/tiger_model
      ln -s /path/to/calibration.pkl models/calibration.pkl
      ln -s /path/to/scoring.pkl models/scoring.pkl
MSG
else
  echo "✅ models/tiger_model present"
fi

echo ""
# Check for reference transcriptome target
echo "[4/4] Verifying transcriptome reference"
REF_FILE="reference/gencode.vM37.transcripts.uc.joined"
if [ -f "$REF_FILE" ]; then
  echo "✅ Reference found: $REF_FILE"
else
  cat <<'MSG'
⚠️  Transcriptome reference not found at reference/gencode.vM37.transcripts.uc.joined
    Provide a symlink or edit config.yaml → offtarget.reference_transcriptome
MSG
fi

# Ship example targets file for new users
echo ""
echo "📄 Writing example targets to targets.example.txt"
cat > targets.example.txt <<'EOF_TARGETS'
# Example targets file
# Add one gene name per line
Nanog
Oct4
Sox2
EOF_TARGETS

# Quick smoke import check (non-fatal)
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('lib')))
try:
    from utils.logger import setup_logger
    from utils.config import load_config
    print('✅ Python module import test passed')
except ImportError as exc:
    print(f'❌ Python import test failed: {exc}')
    sys.exit(1)
PY

cat <<'NEXT'
============================================================
Step 01 complete.
Next: run scripts/02_quick_check.sh for a lightweight verification,
then scripts/03_preflight_check.sh before launching the workflow.
============================================================
NEXT
