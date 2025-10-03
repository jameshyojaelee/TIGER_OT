#!/bin/bash
#
# Setup script for Cas13 TIGER Workflow
# ======================================
#
# This script sets up the complete workflow environment.
#

set -e  # Exit on error

echo "=================================================="
echo "Cas13 TIGER Workflow - Setup"
echo "=================================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo ""

# Step 1: Build C components
echo "Step 1: Building C components..."
make clean
make
echo "✅ C components built"
echo ""

# Step 2: Install Python dependencies
echo "Step 2: Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Python dependencies installed"
echo ""

# Step 3: Set up model symlinks
echo "Step 3: Setting up model symlinks..."

# Check if models directory needs setup
if [ ! -d "models/tiger_model" ]; then
    echo "⚠️  Model directory not found"
    echo "Please create symlinks manually:"
    echo "  ln -s /path/to/tiger_model models/tiger_model"
    echo "  ln -s /path/to/calibration.pkl models/calibration.pkl"
    echo "  ln -s /path/to/scoring.pkl models/scoring.pkl"
else
    echo "✅ Models already configured"
fi
echo ""

# Step 4: Set up reference symlink
echo "Step 4: Setting up reference transcriptome..."

if [ ! -f "reference/gencode.vM37.transcripts.uc.joined" ]; then
    echo "⚠️  Reference transcriptome not found"
    echo "Please create symlink manually:"
    echo "  ln -s /path/to/gencode.vM37.transcripts.uc.joined reference/"
else
    echo "✅ Reference already configured"
fi
echo ""

# Step 5: Create example targets file
echo "📝 Step 5: Creating example targets file..."
cat > targets.example.txt <<EOF
# Example targets file
# Add one gene name per line
Nanog
Oct4
Sox2
EOF
echo "✅ Created targets.example.txt"
echo ""

# Step 6: Test installation
echo "Step 6: Testing installation..."

# Test Python imports
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('lib')))
from utils.logger import setup_logger
from utils.config import load_config
print('✅ Python modules import successfully')
" || echo "❌ Python import test failed"

# Test C binary
if [ -x "bin/offtarget_search" ]; then
    echo "✅ C binary is executable"
else
    echo "❌ C binary not found or not executable"
fi

echo ""
echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Edit targets.txt with your gene names"
echo "  2. Run: python3 run_tiger.py targets.txt"
echo ""
echo "For help:"
echo "  python3 run_tiger.py --help"
echo ""
