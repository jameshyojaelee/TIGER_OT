"""
Validation utilities for TIGER output
"""
import pandas as pd
from pathlib import Path

def validate_tiger_output(csv_path, logger=None):
    """
    Validate TIGER output CSV file
    
    Args:
        csv_path: Path to TIGER output CSV
        logger: Optional logger
        
    Returns:
        bool: True if valid
    """
    try:
        df = pd.read_csv(csv_path)
        
        # Check required columns
        required_cols = ['Gene', 'Sequence', 'Score']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            if logger:
                logger.error(f"Missing columns: {missing_cols}")
            return False
        
        # Check for empty dataframe
        if len(df) == 0:
            if logger:
                logger.error("TIGER output is empty")
            return False
        
        # Check sequence length
        seq_lengths = df['Sequence'].str.len()
        if seq_lengths.min() < 20 or seq_lengths.max() > 30:
            if logger:
                logger.warning(f"Unusual sequence lengths: {seq_lengths.min()}-{seq_lengths.max()}")
        
        # Check score range
        if df['Score'].min() < 0 or df['Score'].max() > 1:
            if logger:
                logger.warning(f"Unusual score range: {df['Score'].min()}-{df['Score'].max()}")
        
        if logger:
            logger.info(f"✅ TIGER output validated: {len(df)} guides")
        
        return True
    
    except Exception as e:
        if logger:
            logger.error(f"Validation error: {e}")
        return False

def check_guide_quality(df, min_score=0.0, logger=None):
    """
    Check quality of guides
    
    Args:
        df: DataFrame with guides
        min_score: Minimum acceptable score
        logger: Optional logger
        
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if logger:
        logger.info(f"Filtering guides with score >= {min_score}...")
    
    filtered = df[df['Score'] >= min_score].copy()
    
    if logger:
        logger.info(f"Kept {len(filtered)}/{len(df)} guides ({100*len(filtered)/len(df):.1f}%)")
    
    return filtered
