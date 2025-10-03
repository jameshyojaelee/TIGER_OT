#!/usr/bin/env python3
"""
Analyze MM0 (perfect match) locations for final guides.
Determines if MM0 matches are in the same gene (different isoforms) or different genes.
"""

import pandas as pd
import sys
from collections import defaultdict

def load_transcriptome_with_genes(fasta_file):
    """Load transcriptome and extract gene names from headers"""
    transcripts = {}
    transcript_to_gene = {}
    transcript_to_name = {}
    current_id = None
    current_seq = []
    
    print(f"Loading reference transcriptome: {fasta_file}")
    with open(fasta_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                # Save previous transcript
                if current_id is not None:
                    transcripts[current_id] = ''.join(current_seq)
                
                # Parse header
                # Format: >TRANSCRIPT_ID|GENE_ID|...|TRANSCRIPT_NAME|GENE_SYMBOL|...
                # Example: >ENSMUST00000193812.2|ENSMUSG00000102693.2|...|4933401J01Rik-201|4933401J01Rik|...
                header = line[1:]
                parts = header.split('|')
                
                transcript_id = parts[0] if len(parts) > 0 else header
                transcript_name = parts[4] if len(parts) > 4 else transcript_id.split('.')[0]  # e.g., "Pnpla2-201"
                gene_symbol = parts[5] if len(parts) > 5 else 'Unknown'  # e.g., "Pnpla2"
                
                current_id = transcript_id
                transcript_to_gene[transcript_id] = gene_symbol
                transcript_to_name[transcript_id] = transcript_name
                current_seq = []
            else:
                current_seq.append(line.upper())
        
        # Save last transcript
        if current_id is not None:
            transcripts[current_id] = ''.join(current_seq)
    
    print(f"Loaded {len(transcripts)} transcripts")
    return transcripts, transcript_to_gene, transcript_to_name

def find_all_matches(target_seq, transcriptome, transcript_to_gene, transcript_names=None):
    """Find all perfect matches of target sequence in transcriptome"""
    matches = []
    
    for transcript_id, seq in transcriptome.items():
        if target_seq in seq:
            gene = transcript_to_gene.get(transcript_id, 'Unknown')
            # Count occurrences in this transcript
            count = seq.count(target_seq)
            
            # Get transcript name from header (like "Pnpla2-201")
            transcript_name = transcript_names.get(transcript_id, transcript_id.split('.')[0])
            
            matches.append({
                'transcript': transcript_id,
                'transcript_name': transcript_name,
                'gene': gene,
                'occurrences': count
            })
    
    return matches

def analyze_mm0_locations(guides_csv, transcriptome_file, output_file):
    """Analyze where MM0 matches are located for each guide"""
    
    # Load data
    guides_df = pd.read_csv(guides_csv)
    transcriptome, transcript_to_gene, transcript_to_name = load_transcriptome_with_genes(transcriptome_file)
    
    print(f"\nAnalyzing {len(guides_df)} guides...")
    
    # Handle different column name conventions
    seq_col = 'Target Sequence' if 'Target Sequence' in guides_df.columns else 'Sequence'
    score_col = 'Guide Score' if 'Guide Score' in guides_df.columns else 'Score'
    
    results = []
    summary_stats = {
        'same_gene_only': 0,
        'different_genes': 0,
        'total_guides': len(guides_df)
    }
    
    for idx, row in guides_df.iterrows():
        target_seq = row[seq_col].upper()
        expected_gene = row['Gene']
        mm0_count = row['MM0']
        guide_score = row[score_col]
        
        # Find all matches
        matches = find_all_matches(target_seq, transcriptome, transcript_to_gene, transcript_to_name)
        
        # Categorize matches (case-insensitive comparison)
        genes_found = set([m['gene'] for m in matches])
        same_gene_matches = [m for m in matches if m['gene'].lower() == expected_gene.lower()]
        other_gene_matches = [m for m in matches if m['gene'].lower() != expected_gene.lower()]
        
        # Get transcript names
        same_gene_transcript_names = [m['transcript_name'] for m in same_gene_matches]
        other_gene_transcript_names = [m['transcript_name'] for m in other_gene_matches]
        
        # Total occurrences
        total_occurrences = sum([m['occurrences'] for m in matches])
        same_gene_occurrences = sum([m['occurrences'] for m in same_gene_matches])
        other_gene_occurrences = sum([m['occurrences'] for m in other_gene_matches])
        
        # Categorize
        if len(other_gene_matches) == 0:
            category = 'SAME_GENE_ONLY'
            summary_stats['same_gene_only'] += 1
        else:
            category = 'DIFFERENT_GENES'
            summary_stats['different_genes'] += 1
        
        result = {
            'Gene': expected_gene,
            'Target Sequence': target_seq[:30] + '...',
            'Guide Score': guide_score,
            'MM0': mm0_count,
            'Total Matches': total_occurrences,
            'Category': category,
            'Matching Transcripts': ', '.join(sorted(same_gene_transcript_names)),
            'Num Transcripts': len(same_gene_matches),
            'Same Gene Occurrences': same_gene_occurrences,
            'Other Gene Transcripts': ', '.join(sorted(other_gene_transcript_names)) if other_gene_matches else '',
            'Other Gene Count': len(other_gene_matches),
            'Other Gene Occurrences': other_gene_occurrences
        }
        results.append(result)
        
        # Print concerning cases
        if other_gene_matches and mm0_count > 2:
            print(f"\n⚠️  {expected_gene}: {mm0_count} matches, {len(other_gene_matches)} in other genes")
            print(f"   Other transcripts: {', '.join([m['transcript_name'] for m in other_gene_matches])}")
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Save detailed results
    results_df.to_csv(output_file, index=False)
    print(f"\n✓ Detailed results saved to: {output_file}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY OF MM0 LOCATIONS")
    print("=" * 70)
    print(f"Total guides analyzed: {summary_stats['total_guides']}")
    print(f"\nMatches only in SAME gene (different isoforms): {summary_stats['same_gene_only']} "
          f"({summary_stats['same_gene_only']/summary_stats['total_guides']*100:.1f}%)")
    print(f"Matches in DIFFERENT genes (potential off-targets): {summary_stats['different_genes']} "
          f"({summary_stats['different_genes']/summary_stats['total_guides']*100:.1f}%)")
    
    # Per-gene summary
    print("\n" + "=" * 70)
    print("PER-GENE BREAKDOWN (Transcript Isoforms)")
    print("=" * 70)
    print(f"{'Gene':<12} {'Guides':<8} {'Max MM0':<8} {'Transcripts Matched'}")
    print("-" * 70)
    
    for gene in sorted(guides_df['Gene'].unique()):
        gene_results = results_df[results_df['Gene'] == gene]
        total = len(gene_results)
        max_mm0 = gene_results['MM0'].max()
        
        # Get all unique transcripts for this gene
        all_transcripts = set()
        for idx, row in gene_results.iterrows():
            if row['Matching Transcripts']:
                all_transcripts.update(row['Matching Transcripts'].split(', '))
        
        transcripts_str = ', '.join(sorted(all_transcripts))
        if len(transcripts_str) > 50:
            transcripts_str = transcripts_str[:47] + '...'
        
        print(f"{gene:<12} {total:<8} {max_mm0:<8} {transcripts_str}")
    
    # Show most concerning guides
    print("\n" + "=" * 70)
    print("MOST CONCERNING GUIDES (matches in other genes)")
    print("=" * 70)
    
    concerning = results_df[results_df['Category'] == 'DIFFERENT_GENES'].sort_values(
        'Other Gene Occurrences', ascending=False).head(10)
    
    if len(concerning) > 0:
        print(f"\n{'Gene':<10} {'Score':<7} {'MM0':<5} {'Other Transcripts':<40} {'Hits'}")
        print("-" * 70)
        for idx, row in concerning.iterrows():
            other_transcripts = row['Other Gene Transcripts'][:38] if len(row['Other Gene Transcripts']) > 38 else row['Other Gene Transcripts']
            print(f"{row['Gene']:<10} {row['Guide Score']:<7.3f} {row['MM0']:<5} "
                  f"{other_transcripts:<40} {row['Other Gene Occurrences']}")
    else:
        print("\n✓ No concerning off-targets found!")
    
    print("\n" + "=" * 70)
    
    return results_df, summary_stats

def validate_final_guides(guides_csv, transcriptome_file, output_file, logger=None):
    """
    Validate final guides by analyzing MM0 locations
    
    Args:
        guides_csv: Path to final guides CSV
        transcriptome_file: Path to reference transcriptome FASTA
        output_file: Path to save validation results
        logger: Optional logger for output
        
    Returns:
        tuple: (results_df, summary_stats)
    """
    if logger:
        logger.info("=" * 70)
        logger.info("MM0 LOCATION ANALYSIS")
        logger.info("=" * 70)
        logger.info("Analyzing where MM0 perfect matches are located...")
        logger.info("This helps identify if matches are in same gene (OK) or different genes (concerning)")
        logger.info("=" * 70)
    else:
        print("=" * 70)
        print("MM0 LOCATION ANALYSIS")
        print("=" * 70)
        print("Analyzing where MM0 perfect matches are located...")
        print("This helps identify if matches are in same gene (OK) or different genes (concerning)")
        print("=" * 70)
    
    results_df, stats = analyze_mm0_locations(guides_csv, transcriptome_file, output_file)
    
    if logger:
        logger.info("\n✓ MM0 location analysis complete!")
    else:
        print("\n✓ Analysis complete!")
    
    return results_df, stats

def main():
    import os
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    guides_csv = os.path.join(script_dir, "top_guides_adaptive.csv")
    transcriptome_file = "/gpfs/commons/home/jameslee/Cas13/TIGER/Issler/gencode.vM37.transcripts.fa"
    output_file = os.path.join(script_dir, "mm0_location_analysis.csv")
    
    validate_final_guides(guides_csv, transcriptome_file, output_file)

if __name__ == "__main__":
    main()
