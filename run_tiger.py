#!/usr/bin/env python3
"""
Cas13 Guide Design - Master Workflow
=====================================
Standalone, optimized pipeline for Cas13 guide RNA design.

Usage:
    python3 run_workflow.py targets.txt --species {human,mouse} [options]

Examples:
    python3 run_workflow.py targets.txt --species mouse
    python3 run_workflow.py targets.txt --species mouse --top-n 5
    python3 run_workflow.py targets.txt --species human --config configs/custom.yaml
"""

import sys
import argparse
from pathlib import Path

# Add source tree to path so "workflows" and helpers resolve when invoked as a script
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from workflows.master import Cas13WorkflowRunner
from utils.logger import setup_logger
from utils.config import load_config

def main():
    parser = argparse.ArgumentParser(
        description="Cas13 Guide Design - Complete Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python3 run_workflow.py targets.txt --species mouse
  
  # Advanced options
  python3 run_workflow.py targets.txt --species mouse --top-n 5 --skip-download
  python3 run_workflow.py targets.txt --species human --config custom.yaml --dry-run
  
  # Resume from specific step
  python3 run_workflow.py targets.txt --species mouse --resume-from offtarget
        """
    )
    
    # Required arguments
    parser.add_argument(
        'targets',
        type=str,
        help='Path to targets.txt file (gene names, one per line)'
    )
    
    parser.add_argument(
        '--species',
        choices=['human', 'mouse'],
        required=True,
        help='Species for guide design (choose human or mouse)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='runs/latest',
        help='Output directory (default: runs/latest)'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='configs/default.yaml',
        help='Configuration file (default: configs/default.yaml)'
    )
    
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top guides per gene (default: 10)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview workflow without executing'
    )
    
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip FASTA download if files exist'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation steps (faster but not recommended)'
    )
    
    parser.add_argument(
        '--resume-from',
        type=str,
        choices=['download', 'tiger', 'offtarget', 'filter'],
        help='Resume workflow from specific step'
    )
    
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Number of threads for parallel processing (default: 4)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_logger(
        'Cas13Workflow',
        verbose=args.verbose,
        log_file=f"{args.output_dir}/workflow.log"
    )
    
    # Load configuration
    main_dir = Path(__file__).parent
    config = load_config(main_dir / args.config)
    
    # Resolve species-specific settings
    species_key = args.species.lower()
    species_options = config.get('species_options', {})
    if species_key not in species_options:
        raise SystemExit(f"Species '{args.species}' is not configured. Available options: {', '.join(species_options)}")

    species_config = species_options[species_key]
    config['selected_species'] = species_key
    config['species'] = species_config['ensembl_name']
    config.setdefault('offtarget', {})['reference_transcriptome'] = species_config['reference_transcriptome']

    logger.info(f"Selected species: {species_key} → {config['species']}")

    # Update config with command-line arguments
    config['top_n_guides'] = args.top_n
    config['output_dir'] = args.output_dir
    config['threads'] = args.threads
    
    # Initialize workflow runner
    runner = Cas13WorkflowRunner(
        targets_file=args.targets,
        config=config,
        main_dir=main_dir,
        dry_run=args.dry_run,
        logger=logger
    )
    
    # Run workflow
    try:
        success = runner.run(
            skip_download=args.skip_download,
            skip_validation=args.skip_validation,
            resume_from=args.resume_from
        )
        
        if success:
            logger.info("✅ Workflow completed successfully!")
            logger.info(f"📄 Results: {args.output_dir}/final_guides.csv")
            sys.exit(0)
        else:
            logger.error("❌ Workflow failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Workflow interrupted by user")
        logger.info("You can resume with: --resume-from <step>")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
