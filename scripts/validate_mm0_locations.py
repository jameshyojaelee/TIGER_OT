#!/usr/bin/env python3
"""
Validate MM0 (perfect match) locations for final guides.

This script analyzes where MM0 matches occur in the transcriptome:
- SAME_GENE_ONLY: All matches are in target gene (different isoforms) ✓
- DIFFERENT_GENES: Some matches are in off-target genes ⚠️

Usage:
    python3 scripts/validate_mm0_locations.py runs/latest/final_guides.csv

    python3 scripts/validate_mm0_locations.py runs/my_run/final_guides.csv \
        --reference resources/reference/gencode.vM37.transcripts.uc.joined \
        --output runs/my_run/mm0_analysis.csv
"""

import sys
import argparse
from pathlib import Path

# Add package to path
ROOT_DIR = Path(__file__).parent.parent  # Go up to TIGER root
PACKAGE_SRC = ROOT_DIR / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists():
    sys.path.insert(0, str(PACKAGE_SRC))

from tiger_guides.tiger.validation import validate_final_guides

def main():
    parser = argparse.ArgumentParser(
        description="Validate MM0 locations for final guides",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze final guides from latest run
  python3 scripts/validate_mm0_locations.py runs/latest/final_guides.csv

  # Specify custom reference and output
  python3 scripts/validate_mm0_locations.py runs/my_run/final_guides.csv \\
      --reference resources/reference/gencode.vM37.transcripts.fa \\
      --output runs/my_run/mm0_detailed.csv

  # Use human reference
  python3 scripts/validate_mm0_locations.py runs/human/final_guides.csv \\
      --reference resources/reference/gencode.v47.transcripts.fa

Output:
  Creates a CSV file with detailed transcript-level analysis showing:
  - Which transcripts each guide matches
  - Whether matches are same gene (isoforms) or different genes (off-targets)
  - Transcript names (e.g., "Actb-201", "Actb-202")
  - Per-transcript occurrence counts

See docs/GUIDE_SELECTION_AND_VALIDATION.md for detailed interpretation guide.
        """
    )

    parser.add_argument(
        'guides_csv',
        type=str,
        help='Path to final_guides.csv file'
    )

    parser.add_argument(
        '--reference', '-r',
        type=str,
        default='resources/reference/gencode.vM37.transcripts.uc.joined',
        help='Path to reference transcriptome FASTA (default: mouse gencode.vM37)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output CSV file path (default: <guides_dir>/mm0_location_analysis.csv)'
    )

    args = parser.parse_args()

    # Resolve paths
    guides_csv = Path(args.guides_csv)
    if not guides_csv.exists():
        print(f"Error: Guides file not found: {guides_csv}")
        sys.exit(1)

    reference_path = Path(args.reference)
    if not reference_path.is_absolute():
        reference_path = ROOT_DIR / reference_path

    if not reference_path.exists():
        print(f"Error: Reference file not found: {reference_path}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = guides_csv.parent / "mm0_location_analysis.csv"

    print("=" * 70)
    print("MM0 LOCATION VALIDATION")
    print("=" * 70)
    print(f"Guides:     {guides_csv}")
    print(f"Reference:  {reference_path}")
    print(f"Output:     {output_path}")
    print("=" * 70)
    print()

    # Run validation
    try:
        results_df, stats = validate_final_guides(
            guides_csv=str(guides_csv),
            transcriptome_file=str(reference_path),
            output_file=str(output_path)
        )

        print("\n" + "=" * 70)
        print("✓ VALIDATION COMPLETE")
        print("=" * 70)
        print(f"Results saved to: {output_path}")
        print()
        print("Next steps:")
        print("  1. Review the CSV file for detailed transcript matches")
        print("  2. Focus on guides with Category=SAME_GENE_ONLY")
        print("  3. Investigate guides with Other_Gene_Count > 0")
        print()
        print("See docs/GUIDE_SELECTION_AND_VALIDATION.md for interpretation guide.")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
