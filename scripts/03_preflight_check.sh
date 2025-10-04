#!/bin/bash
# 03_preflight_check.sh -- full diagnostics prior to running the workflow
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

WRAPPER="${ROOT_DIR}/scripts/00_load_environment.sh"

cat <<'HDR'
╔══════════════════════════════════════════════════════════════════════╗
║         Cas13 TIGER Workflow · Step 03/04 — Pre-Flight Check          ║
╚══════════════════════════════════════════════════════════════════════╝
HDR

echo "This step exercises every dependency before a production run."
echo ""

PASS=0
FAIL=0

section() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

test_pass() { echo "✅ $1"; PASS=$((PASS+1)); }
test_fail() { echo "❌ $1"; FAIL=$((FAIL+1)); }

section "Test 1: Environment Wrapper"
if [ -x "$WRAPPER" ]; then
  test_pass "scripts/00_load_environment.sh exists and is executable"
else
  test_fail "scripts/00_load_environment.sh missing or not executable"
fi

echo ""
section "Test 2: Python Availability"
if "$WRAPPER" python3 --version >/dev/null 2>&1; then
  test_pass "Python accessible via wrapper"
else
  test_fail "Python not reachable through wrapper"
fi

echo ""
section "Test 3: Python Packages"
if "$WRAPPER" python3 -c "
import tensorflow as tf
import yaml
import pandas as pd
import numpy as np
from Bio import SeqIO
import requests
import tqdm
import colorama
print('✅ All required packages available')
print(f'  TensorFlow: {tf.__version__}')
print(f'  NumPy: {np.__version__}')
print(f'  Pandas: {pd.__version__}')
" 2>&1 | grep -v "^2025" | grep -v "To enable" | grep -v "TF-TRT" | grep -v "Unable to register"; then
  test_pass "Python package imports succeeded"
else
  test_fail "Package import failed"
fi

echo ""
section "Test 4: TIGER Core Files"
if [ -f "src/lib/tiger_core/tiger.py" ]; then
  test_pass "TIGER core files present"
else
  test_fail "TIGER core files missing"
fi

echo ""
section "Test 5: TIGER Model Files"
if [ -d "resources/models/tiger_model/model" ] && [ -f "resources/models/tiger_model/calibration_params.pkl" ]; then
  test_pass "TIGER model and calibration parameters present"
else
  test_fail "TIGER model assets missing"
fi

echo ""
section "Test 6: Workflow Entry Point"
if "$WRAPPER" python3 run_tiger.py --help >/dev/null 2>&1; then
  test_pass "run_tiger.py loads successfully"
else
  test_fail "run_tiger.py failed to load"
fi

echo ""
section "Test 7: Configuration File"
CONFIG_FILE="configs/default.yaml"
if [ -f "$CONFIG_FILE" ]; then
  if "$WRAPPER" python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    config = yaml.safe_load(f)
print('✅ Configuration file valid')
print(f'  min_guide_score: {config[\"filtering\"][\"min_guide_score\"]}')
print(f'  mm0_tolerance: {config[\"filtering\"][\"mm0_tolerance\"]}')
print(f'  top_n_guides: {config[\"filtering\"][\"top_n_guides\"]}')
" 2>&1 | grep -v "^2025" | grep -v "To enable" | grep -v "TF-TRT" | grep -v "Unable to register"; then
    test_pass "configs/default.yaml parsed successfully"
  else
    test_fail "configs/default.yaml failed to validate"
  fi
else
  test_fail "configs/default.yaml missing"
fi

echo ""
section "Test 8: Off-Target Search Binary"
if [ -x "bin/offtarget_search" ]; then
  test_pass "Off-target search binary present"
else
  test_fail "Off-target search binary missing (run make)"
fi

echo ""
section "Test 9: Reference Datasets"
REF_INFO=$(
  SCRIPT_DIR="$ROOT_DIR" "$WRAPPER" python3 - <<'PYCONF'
import os
import yaml
from pathlib import Path

root = Path(os.environ['SCRIPT_DIR'])
with open(root / 'configs' / 'default.yaml') as f:
    cfg = yaml.safe_load(f)

species_opts = cfg.get('species_options', {})
if not species_opts:
    print("|MISSING|No species configured|")
else:
    for species, opt in sorted(species_opts.items()):
        ref = Path(opt.get('reference_transcriptome', ''))
        if not ref.is_absolute():
            ref = root / ref

        if ref.exists():
            print(f"{species}|OK|{ref}|")
        elif ref.is_symlink():
            target = ref.resolve(strict=False)
            print(f"{species}|BROKEN|{ref}|{target}")
        else:
            print(f"{species}|MISSING|{ref}|")
PYCONF
)

ref_check_passed=true
while IFS='|' read -r SPECIES REF_STATUS REF_PATH REF_TARGET; do
  [ -z "$SPECIES" ] && continue
  case "$REF_STATUS" in
    OK)
      test_pass "${SPECIES^} transcriptome available: $REF_PATH"
      ;;
    BROKEN)
      [ -n "$REF_TARGET" ] && echo "Symlink target: $REF_TARGET"
      test_fail "${SPECIES^} transcriptome symlink broken: $REF_PATH"
      ref_check_passed=false
      ;;
    MISSING)
      test_fail "${SPECIES^} transcriptome missing: $REF_PATH"
      ref_check_passed=false
      ;;
    *)
      test_fail "Transcriptome check failed: $REF_STATUS"
      ref_check_passed=false
      ;;
  esac
done <<< "$REF_INFO"

if [ "$ref_check_passed" = true ]; then
  :
fi

echo ""
cat <<"SUMMARY"
╔══════════════════════════════════════════════════════════════════════╗
║                        PRE-FLIGHT SUMMARY                            ║
╚══════════════════════════════════════════════════════════════════════╝
SUMMARY

total=$((PASS + FAIL))
echo "Total Tests: $total"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
  cat <<'OK'
All diagnostics passed. Proceed to scripts/04_run_workflow.sh.
OK
  exit 0
else
  cat <<'WARN'
One or more diagnostics failed. Resolve the issues above before running
scripts/04_run_workflow.sh.
WARN
  exit 1
fi
