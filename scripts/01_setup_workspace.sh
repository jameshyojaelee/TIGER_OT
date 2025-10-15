#!/bin/bash
# 01_setup_workspace.sh -- build native components and install Python deps
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"
WRAPPER="${ROOT_DIR}/scripts/00_load_environment.sh"
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
elif [ -d "vendor/venv_packages" ] && [ "$FORCE_PIP" != "1" ]; then
  echo "ℹ️  Found bundled packages under vendor/venv_packages/; skipping pip install."
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
      echo "    If you are on the cluster, rely on modules + bundled vendor/venv_packages or re-run with TIGER_SKIP_PIP=1."
    fi
  fi
  rm -f "$tmp_req"
fi

echo ""
# Check for required model assets and hint if missing
echo "[3/4] Verifying model assets"
MODEL_DIR="resources/models/tiger_model"
if [ ! -d "$MODEL_DIR" ]; then
  cat <<'MSG'
⚠️  Model directory missing: resources/models/tiger_model
    Create symlinks to your TIGER model assets, for example:
      ln -s /path/to/tiger_model resources/models/tiger_model
      ln -s /path/to/calibration_params.pkl resources/models/tiger_model/calibration_params.pkl
      ln -s /path/to/scoring_params.pkl resources/models/tiger_model/scoring_params.pkl
MSG
else
  echo "✅ resources/models/tiger_model present"
fi

echo ""
# Check for reference transcriptome targets
echo "[4/4] Verifying transcriptome references"

MOUSE_REF="resources/reference/gencode.vM37.transcripts.uc.joined"
if [ -f "$MOUSE_REF" ]; then
  echo "✅ Mouse transcriptome found: $MOUSE_REF"
else
  cat <<'MSG'
⚠️  Mouse transcriptome not found at resources/reference/gencode.vM37.transcripts.uc.joined
    Provide a symlink or copy your lab's transcriptome to the path above.
MSG
fi

HUMAN_REF="resources/reference/gencode.v47.transcripts.fa"
HUMAN_SRC="/gpfs/commons/home/jameslee/reference_genome/refdata-gex-GRCh38-2024-A/genome/gencode.v47.transcripts.fa.gz"

if [ -f "$HUMAN_REF" ]; then
  echo "✅ Human transcriptome found: $HUMAN_REF"
else
  if [ -f "$HUMAN_SRC" ]; then
    echo "ℹ️  Human transcriptome missing locally; copying from $HUMAN_SRC (this may take a few minutes)..."
    mkdir -p "$(dirname "$HUMAN_REF")"
    if gzip -dc "$HUMAN_SRC" > "$HUMAN_REF"; then
      echo "✅ Human transcriptome copied to $HUMAN_REF"
    else
      echo "❌ Failed to copy human transcriptome. Remove any partial file and retry."
      rm -f "$HUMAN_REF"
    fi
  else
    cat <<'MSG'
⚠️  Human transcriptome not found. Expected source at:
    /gpfs/commons/home/jameslee/reference_genome/refdata-gex-GRCh38-2024-A/genome/gencode.v47.transcripts.fa.gz
    Copy or symlink the file to resources/reference/gencode.v47.transcripts.fa.
MSG
  fi
fi

# Ship example targets file for new users
echo ""
EXAMPLE_TARGETS="examples/targets/example_targets.txt"
mkdir -p "$(dirname "$EXAMPLE_TARGETS")"
echo "📄 Writing example targets to ${EXAMPLE_TARGETS}"
cat > "$EXAMPLE_TARGETS" <<'EOF_TARGETS'
# Example targets file
# Add one gene name per line
Abcb11
Abhd5
Pnpla3
Pcsk9
Plin3
Plin2
Pnpla2
EOF_TARGETS

# Quick smoke import check (non-fatal)
if "${PY_CMD[@]}" - <<'PY'; then
import sys
from pathlib import Path
sys.path.insert(0, str(Path('tiger_guides_pkg') / 'src'))
sys.path.insert(0, str(Path('src')))
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
