#!/bin/bash
# Quick setup verification script

echo "Checking Cas13 Workflow Setup..."
echo "================================="
echo ""

# Check C binary
if [ -x "bin/offtarget_search" ]; then
    echo "✅ C binary: bin/offtarget_search"
else
    echo "❌ C binary not found or not executable"
    echo "   Run: make"
fi

# Check Python modules
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('lib')))
try:
    from utils.logger import setup_logger
    from utils.config import load_config
    from download.ensembl import EnsemblDownloader
    print('✅ Python modules import successfully')
except ImportError as e:
    print(f'❌ Python import error: {e}')
    print('   Run: pip install --user -r requirements.txt')
" 2>&1

# Check model
if [ -d "models/tiger_model" ] || [ -L "models/tiger_model" ]; then
    echo "✅ TIGER model: models/tiger_model"
else
    echo "⚠️  TIGER model not found"
    echo "   Run: ln -s /path/to/tiger_model models/tiger_model"
fi

# Check reference
REF_LINK="reference/gencode.vM37.transcripts.uc.joined"
if [ -f "$REF_LINK" ]; then
    echo "✅ Reference: $REF_LINK"
elif [ -L "$REF_LINK" ]; then
    TARGET=$(readlink "$REF_LINK")
    if [ -e "$REF_LINK" ]; then
        echo "✅ Reference symlink resolved: $REF_LINK -> $TARGET"
    else
        echo "⚠️  Reference symlink broken: $REF_LINK -> $TARGET"
        echo "   Update the link or point config.yaml at a valid transcriptome."
        echo "   For quick smoke tests you can use config.sample.yaml (bundled tiny reference)."
    fi
else
    echo "⚠️  Reference transcriptome not found"
    echo "   Provide the transcriptome and update config.yaml (offtarget.reference_transcriptome)."
    echo "   For quick smoke tests you can use config.sample.yaml (bundled tiny reference)."
fi

# Check TensorFlow
python3 -c "
try:
    import tensorflow as tf
    print(f'✅ TensorFlow: {tf.__version__}')
except ImportError:
    print('⚠️  TensorFlow not installed')
    print('   Run: pip install --user tensorflow')
" 2>&1

# Check targets file
if [ -f "targets.txt" ]; then
    n_targets=$(grep -v '^#' targets.txt | grep -v '^$' | wc -l)
    echo "✅ Targets file: $n_targets genes"
else
    echo "⚠️  No targets.txt file"
    echo "   Run: cp targets.example.txt targets.txt"
fi

echo ""
echo "Setup check complete!"
echo "Run: ./run_tiger_workflow.sh --help"
