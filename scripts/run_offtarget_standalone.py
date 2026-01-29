#!/usr/bin/env python3
"""
Run standard TIGER off-target search on an arbitrary CSV file.
Supports automatic format conversion for Li_et_al style inputs.
"""
import sys
import argparse
from pathlib import Path
import pandas as pd

# Add package to path
ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGE_SRC = ROOT_DIR / 'tiger_guides_pkg' / 'src'
if PACKAGE_SRC.exists():
    sys.path.insert(0, str(PACKAGE_SRC))

from tiger_guides.offtarget.search import OffTargetSearcher
from tiger_guides.logging import setup_logger

def parse_args():
    parser = argparse.ArgumentParser(description="Run off-target search on guides CSV")
    parser.add_argument("input_csv", type=str, help="Input CSV with guide sequences")
    parser.add_argument("output_csv", type=str, help="Output CSV for results")
    parser.add_argument("--species", type=str, choices=["mouse", "human"], default="mouse", help="Species (default: mouse)")
    parser.add_argument("--threads", type=int, help="Number of threads to use")
    return parser.parse_args()

def load_and_standardize_csv(input_path, logger):
    """
    Load CSV and ensure it has Gene and Sequence columns.
    Handles Li_et_al style headerless files.
    """
    try:
        # Try reading with header first
        df = pd.read_csv(input_path)
        
        # Check if it looks like the Li_et_al file (headerless, 2 columns)
        # Unique characteristic: First row looks like data, not header
        # Example first line: "NT crRNA,TCACCAGAAGCGTACCATACTC"
        if len(df.columns) == 2 and 'NT crRNA' in df.columns[0]:
            # It's likely the specific file we're targeting, but pandas read the first line as header
            # Reload without header
            logger.info("Detected potential headerless file format. Reloading...")
            df = pd.read_csv(input_path, header=None, names=['Gene', 'Sequence'])
        
        # If headers are missing or weird (like 0, 1 from read_csv default)
        elif 'Gene' not in df.columns or 'Sequence' not in df.columns:
            # Fallback: if 2 columns, assume Gene, Sequence
            if len(df.columns) == 2:
                logger.warning(f"Input columns {df.columns.tolist()} do not match 'Gene', 'Sequence'. Assuming {df.columns[0]} is Gene and {df.columns[1]} is Sequence.")
                df.columns = ['Gene', 'Sequence']
            else:
                raise ValueError(f"Input file must have 'Gene' and 'Sequence' columns. Found: {df.columns.tolist()}")

        return df

    except Exception as e:
        logger.error(f"Failed to load input file: {e}")
        raise

def main():
    args = parse_args()
    logger = setup_logger(verbose=True)

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    # 1. Load and Standardize Input
    logger.info(f"Loading guides from {input_path}...")
    guides_df = load_and_standardize_csv(input_path, logger)
    
    # Calculate Target (Reverse Complement)
    logger.info("Calculating Target sequences (reverse complement)...")
    trans_table = str.maketrans("ACGTUacgtu", "TGCAAtgcaa")
    
    def get_rc(seq):
        return seq.translate(trans_table)[::-1]
        
    guides_df['Target'] = guides_df['Sequence'].apply(get_rc)
    
    logger.info(f"Loaded {len(guides_df)} guides.")

    # 2. Setup Searcher
    if args.species == "mouse":
        ref_path = ROOT_DIR / "resources/reference/gencode.vM37.transcripts.fa"
    elif args.species == "human":
        ref_path = ROOT_DIR / "resources/reference/gencode.v47.transcripts.fa"
    
    if not ref_path.exists():
        logger.error(f"Reference file not found: {ref_path}")
        sys.exit(1)

    binary_path = ROOT_DIR / "bin/offtarget_search"
    
    searcher = OffTargetSearcher(
        binary_path=binary_path,
        reference_path=ref_path,
        logger=logger,
        threads=args.threads
    )

    # 3. Run Search
    logger.info(f"Running off-target search ({args.species})...")
    searcher.search(
        guides_df=guides_df,
        output_path=output_path
    )
    
    logger.info("Done.")

if __name__ == "__main__":
    main()
