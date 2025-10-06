#!/usr/bin/env python3
"""
Test a single NT sequence for off-targets
"""
import sys
from pathlib import Path
import pandas as pd

# Add package to path
ROOT_DIR = Path(__file__).parent.parent.parent  # Go up to TIGER root
PACKAGE_SRC = ROOT_DIR / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists():
    sys.path.insert(0, str(PACKAGE_SRC))

from tiger_guides.offtarget.search import OffTargetSearcher
from tiger_guides.logging import setup_logger

def main():
    # Setup
    logger = setup_logger(verbose=True)

    # Test with just 3 sequences
    sequences = [
        'AAGCCCAATAAACCACTCTGACT',
        'GGCCGAATAGGGATATAGGCAAC',
        'AGCCGCAGTAAGGCACAATACCT'
    ]

    logger.info(f"Testing {len(sequences)} candidate sequences")

    # Create DataFrame expected by OffTargetSearcher
    guides_df = pd.DataFrame({
        'Gene': [f'NT_test_{i+1}' for i in range(len(sequences))],
        'Sequence': sequences
    })

    # Initialize searcher
    binary_path = ROOT_DIR / "bin/offtarget_search"
    reference_path = ROOT_DIR / "resources/reference/gencode.vM37.transcripts.uc.joined"

    searcher = OffTargetSearcher(
        binary_path=binary_path,
        reference_path=reference_path,
        logger=logger
    )

    # Run search
    logger.info("Running off-target search...")
    output_dir = ROOT_DIR / "runs/nt_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = searcher.search(
        guides_df=guides_df,
        output_path=output_dir / "test_results.csv"
    )

    # Display results
    logger.info("\nResults:")
    for idx, row in results.iterrows():
        logger.info(f"{row['Sequence']} - MM0:{row['MM0']} MM1:{row['MM1']} MM2:{row['MM2']}")

if __name__ == '__main__':
    main()
