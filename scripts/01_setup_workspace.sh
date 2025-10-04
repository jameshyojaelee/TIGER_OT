#!/bin/bash
# 01_setup_workspace.sh -- build native components and install Python deps
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"
WRAPPER="${ROOT_DIR}/run_with_tiger_env.sh"
if [ -x "$WRAPPER" ]; then
  PY_CMD=("$WRAPPER" python3)
else
  PY_CMD=(python3)
fi

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
# Install Python dependencies (skip when bundled packages already exist)
echo "[2/4] Installing Python dependencies from requirements.txt"

FORCE_PIP=${TIGER_FORCE_PIP:-0}
SKIP_PIP=${TIGER_SKIP_PIP:-0}
SKIP_TF=${TIGER_SKIP_TF_PIP:-1}
PIP_SCOPE=${TIGER_PIP_SCOPE:-user}
PIP_TARGET=${TIGER_PIP_TARGET:-}

if [ "$SKIP_PIP" = "1" ]; then
  echo "ℹ️  Skipping pip install (TIGER_SKIP_PIP=1)."
elif [ -d "venv_packages" ] && [ "$FORCE_PIP" != "1" ]; then
  echo "ℹ️  Found bundled packages under venv_packages/; skipping pip install."
  echo "    Set TIGER_FORCE_PIP=1 to force a reinstall."
else
  tmp_req=$(mktemp)
  if [ "$SKIP_TF" = "1" ]; then
    grep -Ev '^(tensorflow|tensorflow-cpu|keras)' requirements.txt > "$tmp_req"
  else
    cp requirements.txt "$tmp_req"
  fi

  if [ ! -s "$tmp_req" ]; then
    echo "ℹ️  No packages to install after filtering requirements; skipping pip install."
  else
    if [ -n "${TIGER_PIP_CMD:-}" ]; then
      read -r -a PIP_CMD <<<"${TIGER_PIP_CMD}"
    else
      PIP_CMD=(python3 -m pip)
    fi

    PIP_ARGS=(install --no-cache-dir --upgrade)
    if [ -n "$PIP_TARGET" ]; then
      PIP_ARGS+=(--target "$PIP_TARGET")
    elif [ "$PIP_SCOPE" != "system" ]; then
      PIP_ARGS+=(--user)
    fi
    PIP_ARGS+=(-r "$tmp_req")

    echo "    Command: ${PIP_CMD[*]} ${PIP_ARGS[*]}"
    if "${PIP_CMD[@]}" "${PIP_ARGS[@]}"; then
      echo "✅ Python dependencies installed"
    else
      echo "⚠️  pip install failed."
      echo "    If you are on the cluster, rely on modules + bundled venv_packages or re-run with TIGER_SKIP_PIP=1."
    fi
  fi
  rm -f "$tmp_req"
fi

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
if "${PY_CMD[@]}" - <<'PY'; then
import sys
from pathlib import Path
sys.path.insert(0, str(Path('lib')))
from utils.logger import setup_logger  # noqa: F401
from utils.config import load_config  # noqa: F401
print('✅ Python module import test passed')
PY
  :
else
  echo "❌ Python import test failed (see traceback above)"
  exit 1
fi

cat <<'NEXT'
============================================================
Step 01 complete.
Next: run scripts/02_quick_check.sh for a lightweight verification,
then scripts/03_preflight_check.sh before launching the workflow.
============================================================
NEXT
