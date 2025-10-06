#!/usr/bin/env python3
"""
Test NT candidate sequences for off-targets
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

    # Load candidates
    candidates_file = ROOT_DIR / "examples/targets/NT_candidates.txt"
    with open(candidates_file, 'r') as f:
        sequences = [line.strip() for line in f if line.strip()]

    logger.info(f"Loaded {len(sequences)} candidate sequences")

    # Create DataFrame expected by OffTargetSearcher
    guides_df = pd.DataFrame({
        'Gene': [f'NT_cand_{i+1:02d}' for i in range(len(sequences))],
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
    output_dir = ROOT_DIR / "runs/nt_validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = searcher.search(
        guides_df=guides_df,
        output_path=output_dir / "nt_candidates_offtarget.csv"
    )

    # Analyze results
    logger.info("\n" + "="*60)
    logger.info("OFF-TARGET ANALYSIS RESULTS")
    logger.info("="*60)

    # Filter for guides with zero off-targets
    zero_mm0 = results[results['MM0'] == 0]
    zero_mm1 = results[results['MM1'] == 0]
    zero_mm2 = results[results['MM2'] == 0]

    perfect_candidates = results[
        (results['MM0'] == 0) &
        (results['MM1'] == 0) &
        (results['MM2'] == 0)
    ]

    logger.info(f"Total candidates: {len(results)}")
    logger.info(f"Candidates with MM0=0: {len(zero_mm0)}")
    logger.info(f"Candidates with MM1=0: {len(zero_mm1)}")
    logger.info(f"Candidates with MM2=0: {len(zero_mm2)}")
    logger.info(f"Perfect candidates (MM0=MM1=MM2=0): {len(perfect_candidates)}")

    if len(perfect_candidates) >= 7:
        logger.info(f"\n✅ SUCCESS: Found {len(perfect_candidates)} perfect NT candidates!")
        logger.info("\nTop 7 candidates to add to NT.txt:")
        for idx, row in perfect_candidates.head(7).iterrows():
            logger.info(f"  {row['Sequence']}")

        # Save the perfect candidates
        perfect_candidates.to_csv(
            output_dir / "perfect_nt_candidates.csv",
            index=False
        )
        logger.info(f"\n💾 Saved perfect candidates to {output_dir}/perfect_nt_candidates.csv")

    else:
        logger.warning(f"\n⚠️  Only found {len(perfect_candidates)} perfect candidates (need 7)")
        logger.info("\nCandidates with lowest off-target counts:")
        results_sorted = results.sort_values(['MM0', 'MM1', 'MM2'])
        for idx, row in results_sorted.head(10).iterrows():
            logger.info(f"  {row['Sequence']} - MM0:{row['MM0']} MM1:{row['MM1']} MM2:{row['MM2']}")

    logger.info("\n" + "="*60)

if __name__ == '__main__':
    main()
