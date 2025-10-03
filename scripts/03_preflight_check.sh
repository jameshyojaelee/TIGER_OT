#!/bin/bash
################################################################################
# Pre-Flight Check for TIGER Workflow
# Tests all components before running the full workflow
################################################################################

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║         TIGER Workflow Pre-Flight Check                             ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

# Test 1: Check wrapper script
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Wrapper Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -x "./run_with_tiger_env.sh" ]; then
    echo "✅ run_with_tiger_env.sh exists and is executable"
    ((PASS++))
else
    echo "❌ run_with_tiger_env.sh missing or not executable"
    ((FAIL++))
fi
echo ""

# Test 2: Check Python and modules
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Python Environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./run_with_tiger_env.sh python3 --version && {
    echo "✅ Python accessible"
    ((PASS++))
} || {
    echo "❌ Python not found"
    ((FAIL++))
}
echo ""

# Test 3: Check Python packages
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: Python Packages"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./run_with_tiger_env.sh python3 -c "
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
" 2>&1 | grep -v "^2025" | grep -v "To enable" | grep -v "TF-TRT" | grep -v "Unable to register" && {
    ((PASS++))
} || {
    echo "❌ Package import failed"
    ((FAIL++))
}
echo ""

# Test 4: Check TIGER core files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: TIGER Core Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "lib/tiger_core/tiger.py" ]; then
    echo "✅ TIGER core files present"
    ((PASS++))
else
    echo "❌ TIGER core files missing"
    ((FAIL++))
fi
echo ""

# Test 5: Check TIGER model
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 5: TIGER Model Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "models/tiger_model/model" ] && [ -f "models/tiger_model/calibration_params.pkl" ]; then
    echo "✅ TIGER model and parameters present"
    ((PASS++))
else
    echo "❌ TIGER model files missing"
    ((FAIL++))
fi
echo ""

# Test 6: Check workflow imports
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 6: Workflow Imports"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./run_with_tiger_env.sh python3 run_tiger.py --help > /dev/null 2>&1 && {
    echo "✅ Workflow script loads successfully"
    ((PASS++))
} || {
    echo "❌ Workflow script failed to load"
    ((FAIL++))
}
echo ""

# Test 7: Check configuration
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 7: Configuration File"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "config.yaml" ]; then
    ./run_with_tiger_env.sh python3 -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
print('✅ Configuration file valid')
print(f'  min_guide_score: {config[\"filtering\"][\"min_guide_score\"]}')
print(f'  mm0_tolerance: {config[\"filtering\"][\"mm0_tolerance\"]}')
print(f'  top_n_guides: {config[\"filtering\"][\"top_n_guides\"]}')
" 2>&1 | grep -v "^2025" | grep -v "To enable" | grep -v "TF-TRT" | grep -v "Unable to register" && {
        ((PASS++))
    } || {
        echo "❌ Configuration file invalid"
        ((FAIL++))
    }
else
    echo "❌ config.yaml not found"
    ((FAIL++))
fi
echo ""

# Test 8: Check C binary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 8: Off-Target Search Binary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -x "bin/offtarget_search" ]; then
    echo "✅ Off-target search binary exists"
    ((PASS++))
else
    echo "❌ Off-target search binary missing"
    echo "   Run 'make' to build it"
    ((FAIL++))
fi
echo ""

# Test 9: Reference Dataset
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 9: Reference Dataset"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
REF_INFO=$(SCRIPT_DIR="${SCRIPT_DIR}" ./run_with_tiger_env.sh python3 - <<'PYCONF'
import os
import yaml
from pathlib import Path
root = Path(os.environ['SCRIPT_DIR'])
with open(root / 'config.yaml') as f:
    cfg = yaml.safe_load(f)
ref = Path(cfg['offtarget']['reference_transcriptome'])
if not ref.is_absolute():
    ref = root / ref
if ref.exists():
    print(f"OK|{ref}")
elif ref.is_symlink():
    target = ref.resolve(strict=False)
    print(f"BROKEN|{ref}|{target}")
else:
    print(f"MISSING|{ref}|")
PYCONF
)
IFS='|' read -r REF_STATUS REF_PATH REF_TARGET <<<"$REF_INFO"
if [ "$REF_STATUS" = "OK" ]; then
    echo "✅ Reference available: $REF_PATH"
    ((PASS++))
elif [ "$REF_STATUS" = "BROKEN" ]; then
    echo "❌ Reference symlink broken: $REF_PATH → $REF_TARGET"
    echo "   Fix by updating config.yaml or recreating the symlink."
    ((FAIL++))
else
    echo "❌ Reference file missing: $REF_PATH"
    echo "   Provide the full transcriptome or update config.yaml."
    echo "   For smoke tests, use config.sample.yaml (bundled tiny reference)."
    ((FAIL++))
fi
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                        TEST SUMMARY                                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Total Tests: $((PASS + FAIL))"
echo "Passed: $PASS ✅"
echo "Failed: $FAIL ❌"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                      ║"
    echo "║  🎉 ALL TESTS PASSED! Workflow is ready to use!                    ║"
    echo "║                                                                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "To run the workflow:"
    echo "  ./run_tiger_workflow.sh targets.txt"
    echo ""
    exit 0
else
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                      ║"
    echo "║  ⚠️  SOME TESTS FAILED - Please fix issues above                   ║"
    echo "║                                                                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi
