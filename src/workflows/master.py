"""
Master Workflow Orchestrator for Cas13 Guide Design
"""
import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm

# Add parent lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from download.ensembl import EnsemblDownloader
from tiger.predictor import TIGERPredictor
from tiger.validator import validate_tiger_output, check_guide_quality
from offtarget.wrapper import OffTargetSearcher
from utils.slurm import wait_for_jobs
from utils.config import save_config

class Cas13WorkflowRunner:
    """Master workflow runner for Cas13 guide design"""
    
    def __init__(self, targets_file, config, main_dir, dry_run=False, logger=None):
        """
        Initialize workflow runner
        
        Args:
            targets_file: Path to targets.txt (gene names, one per line)
            config: Configuration dictionary
            main_dir: Main directory path
            dry_run: If True, only print steps without executing
            logger: Logger instance
        """
        self.targets_file = Path(targets_file)
        self.config = config
        self.main_dir = Path(main_dir)
        self.dry_run = dry_run
        self.logger = logger
        
        # Set up output directory
        self.output_dir = Path(config['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load target genes
        self.targets = self._load_targets()
        
        # Initialize components
        self.downloader = None
        self.tiger = None
        self.offtarget = None
    
    def _load_targets(self):
        """Load target gene list"""
        if not self.targets_file.exists():
            raise FileNotFoundError(f"Targets file not found: {self.targets_file}")
        
        with open(self.targets_file, 'r') as f:
            targets = [line.strip() for line in f if line.strip()]
        
        if self.logger:
            self.logger.info(f"Loaded {len(targets)} target genes")
        
        return targets
    
    def run(self, skip_download=False, skip_validation=False, resume_from=None):
        """
        Run complete workflow
        
        Args:
            skip_download: Skip download if FASTA exists
            skip_validation: Skip validation steps
            resume_from: Resume from specific step
            
        Returns:
            bool: True if successful
        """
        if self.logger:
            self.logger.info("=" * 60)
            self.logger.info("Cas13 Guide Design Workflow")
            self.logger.info("=" * 60)
        
        # Save configuration
        config_file = self.output_dir / 'config.yaml'
        save_config(self.config, config_file)
        
        if self.dry_run:
            self._print_workflow_plan()
            return True
        
        try:
            # Step 1: Download FASTA sequences
            if not resume_from or resume_from == 'download':
                fasta_file = self._step_download(skip_download)
                if not fasta_file:
                    return False
            else:
                fasta_file = self.output_dir / 'sequences' / 'all_targets.fasta'
            
            # Step 2: Run TIGER prediction
            if not resume_from or resume_from in ['download', 'tiger']:
                tiger_output = self._step_tiger(fasta_file, skip_validation)
                if tiger_output is None:
                    return False
            else:
                tiger_output = self.output_dir / 'tiger' / 'guides.csv'
            
            # Step 3: Run off-target analysis
            if not resume_from or resume_from in ['download', 'tiger', 'offtarget']:
                offtarget_output = self._step_offtarget(tiger_output)
                if offtarget_output is None:
                    return False
            else:
                offtarget_output = self.output_dir / 'offtarget' / 'results.csv'
            
            # Step 4: Filter and rank guides
            if not resume_from or resume_from in ['download', 'tiger', 'offtarget', 'filter']:
                final_output = self._step_filter(offtarget_output)
                if final_output is None:
                    return False
            
            if self.logger:
                self.logger.info("=" * 60)
                self.logger.info("✅ Workflow completed successfully!")
                self.logger.info(f"📄 Final results: {final_output}")
                self.logger.info("=" * 60)
            
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Workflow failed: {e}", exc_info=True)
            return False
    
    def _step_download(self, skip_download):
        """Step 1: Download FASTA sequences"""
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("STEP 1: Download FASTA Sequences")
            self.logger.info("=" * 60)
        
        seq_dir = self.output_dir / 'sequences'
        seq_dir.mkdir(exist_ok=True)
        
        fasta_file = seq_dir / 'all_targets.fasta'
        
        if skip_download and fasta_file.exists():
            if self.logger:
                self.logger.info(f"⏭️  Skipping download (file exists): {fasta_file}")
            return fasta_file
        
        # Initialize downloader
        self.downloader = EnsemblDownloader(
            species=self.config['species'],
            rest_url=self.config['ensembl']['rest_url'],
            rate_limit_delay=self.config['ensembl']['rate_limit_delay'],
            logger=self.logger
        )
        
        # Download sequences
        records = self.downloader.download_genes(
            gene_list=self.targets,
            seq_type='cds',
            output_fasta=fasta_file,
            output_dir=seq_dir / 'individual'
        )
        
        if not records:
            if self.logger:
                self.logger.error("Failed to download any sequences")
            return None
        
        if self.logger:
            self.logger.info(f"✅ Downloaded {len(records)} sequences")
        
        return fasta_file
    
    def _step_tiger(self, fasta_file, skip_validation):
        """Step 2: Run TIGER prediction"""
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("STEP 2: TIGER Guide Prediction")
            self.logger.info("=" * 60)
        
        tiger_dir = self.output_dir / 'tiger'
        tiger_dir.mkdir(exist_ok=True)
        
        output_file = tiger_dir / 'guides.csv'
        
        # Initialize TIGER
        tiger_config = self.config['tiger']
        model_path = self.main_dir / tiger_config['model_path']
        
        self.tiger = TIGERPredictor(
            model_path=model_path,
            config=tiger_config,
            logger=self.logger
        )
        
        # Run prediction
        guides_df = self.tiger.predict_from_fasta(
            fasta_path=fasta_file,
            output_path=output_file,
            batch_size=tiger_config['batch_size']
        )
        
        # Validate output
        if not skip_validation:
            if not validate_tiger_output(output_file, self.logger):
                if self.logger:
                    self.logger.error("TIGER output validation failed")
                return None
        
        if self.logger:
            self.logger.info(f"✅ Generated {len(guides_df)} guides")
        
        return output_file
    
    def _step_offtarget(self, tiger_output):
        """Step 3: Run off-target analysis"""
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("STEP 3: Off-Target Analysis")
            self.logger.info("=" * 60)
        
        offtarget_dir = self.output_dir / 'offtarget'
        offtarget_dir.mkdir(exist_ok=True)
        
        # Load TIGER guides
        guides_df = pd.read_csv(tiger_output)
        
        # Initialize off-target searcher
        offtarget_config = self.config['offtarget']
        binary_path = self.main_dir / offtarget_config['binary_path']
        reference_path = self.main_dir / offtarget_config['reference_transcriptome']
        
        self.offtarget = OffTargetSearcher(
            binary_path=binary_path,
            reference_path=reference_path,
            logger=self.logger
        )
        
        # Run search
        results_df = self.offtarget.search(
            guides_df=guides_df,
            output_path=offtarget_dir / 'results.csv',
            chunk_size=offtarget_config.get('chunk_size')
        )
        
        if self.logger:
            self.logger.info(f"✅ Completed off-target search for {len(results_df)} guides")
        
        return offtarget_dir / 'results.csv'
    
    def _step_filter(self, offtarget_output):
        """
        Step 4: Filter and rank guides
        
        Multi-step filtering approach:
        1. Filter by minimum guide score threshold
        2. Apply adaptive MM0 filtering (minimum MM0 per gene)
        3. Select top N guides per gene by score
        """
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("STEP 4: Filter and Rank Guides")
            self.logger.info("=" * 60)
        
        # Load results
        df = pd.read_csv(offtarget_output)
        
        if self.logger:
            self.logger.info(f"Loaded {len(df)} guides with off-target counts")
            self.logger.info(f"Guide score range: {df['Score'].min():.3f} - {df['Score'].max():.3f}")
        
        # CHECK FOR INVALID GUIDES (MM0=0)
        # A valid guide must match at least its intended target (MM0 >= 1)
        invalid_guides = df[df['MM0'] == 0]
        if len(invalid_guides) > 0:
            if self.logger:
                self.logger.warning("=" * 60)
                self.logger.warning("⚠️  INVALID GUIDES DETECTED (MM0=0)")
                self.logger.warning("=" * 60)
                self.logger.warning(f"Found {len(invalid_guides)} guides with MM0=0")
                self.logger.warning("These guides don't match ANYTHING in the reference (not even their target)")
                self.logger.warning("This usually means off-target search failed for these guides")
                
                by_gene = invalid_guides.groupby('Gene').size()
                self.logger.warning("\nBreakdown by gene:")
                for gene, count in by_gene.items():
                    self.logger.warning(f"  {gene}: {count} guides")
                self.logger.warning("\nThese guides will be EXCLUDED from filtering.\n")
        
        # Get filtering configuration
        filtering_config = self.config['filtering']
        min_score = filtering_config.get('min_guide_score', 0.0)
        
        # STEP 1: Filter by guide score FIRST
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(f"STEP 4.1: Filter by Guide Score (>= {min_score})")
            self.logger.info("=" * 60)
        
        high_score_guides = df[df['Score'] >= min_score].copy()
        
        if self.logger:
            self.logger.info(f"Guides passing score threshold: {len(high_score_guides):,} / {len(df):,}")
        
        # Check which genes have no high-scoring guides
        genes_with_guides = high_score_guides.groupby('Gene').size()
        all_genes = df['Gene'].unique()
        genes_without_guides = [g for g in all_genes if g not in genes_with_guides.index]
        
        if genes_without_guides and self.logger:
            self.logger.warning(f"\n⚠️  {len(genes_without_guides)} genes have NO guides with score >= {min_score}:")
            for gene in genes_without_guides:
                gene_df = df[df['Gene'] == gene]
                max_score = gene_df['Score'].max()
                self.logger.warning(f"  {gene}: max score = {max_score:.3f}")
            self.logger.warning(f"\nConsider lowering min_guide_score in config.yaml if you need guides for these genes.\n")
        
        # STEP 2: Apply off-target and MM0 filters (on high-scoring guides only)
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(f"STEP 4.2: Apply MM Filters (from high-scoring guides only)")
            self.logger.info("=" * 60)
        
        # Filter by off-target thresholds
        # CRITICAL: Require MM0 >= 1 (guide must match at least its intended target)
        filtered = high_score_guides[
            (high_score_guides['MM0'] >= 1) &
            (high_score_guides['MM1'] <= filtering_config['mm1_threshold']) &
            (high_score_guides['MM2'] <= filtering_config['mm2_threshold'])
        ].copy()
        
        if self.logger:
            self.logger.info(f"After MM0>=1, MM1<={filtering_config['mm1_threshold']}, MM2<={filtering_config['mm2_threshold']} filtering: {len(filtered)} guides")
        
        # Apply adaptive MM0 threshold if enabled
        if filtering_config['adaptive_mm0']:
            filtered = self._apply_adaptive_mm0(filtered)
        
        # STEP 3: Select top N guides per gene by score
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(f"STEP 4.3: Select Top {self.config['top_n_guides']} Guides per Gene by Score")
            self.logger.info("=" * 60)
        
        top_n = self.config['top_n_guides']
        
        top_guides = (
            filtered
            .sort_values(['Gene', 'Score'], ascending=[True, False])
            .groupby('Gene')
            .head(top_n)
            .reset_index(drop=True)
        )
        
        if self.logger:
            self.logger.info(f"Final selection: {len(top_guides)} guides")
        
        # Save final output
        output_file = self.output_dir / 'final_guides.csv'
        top_guides.to_csv(output_file, index=False)
        
        if self.logger:
            self.logger.info(f"\n💾 Saved final guides to {output_file}")
            
            # Print summary statistics
            self._print_summary(top_guides)
        
        # Optional: Validate MM0 locations
        if self.config.get('output', {}).get('validate_mm0_locations', False):
            self._step_validate_mm0(output_file)
        
        return output_file
    
    def _apply_adaptive_mm0(self, df):
        """
        Apply adaptive MM0 threshold per gene with tolerance
        
        For each gene, select guides with MM0 in range [min_MM0, min_MM0 + tolerance].
        This allows genes with unavoidable duplications to still have guides,
        while preferring the most specific guides available for each gene.
        
        Note: Input df already filtered for MM0 >= 1 (valid guides only)
        """
        filtering_config = self.config['filtering']
        mm0_tolerance = filtering_config.get('mm0_tolerance', 0)
        
        if mm0_tolerance == 999:
            if self.logger:
                self.logger.info("MM0 filtering: DISABLED (using only MM1=0, MM2=0)")
            return df
        
        if self.logger:
            if mm0_tolerance == 0:
                self.logger.info("Applying adaptive MM0 threshold (strict minimum MM0 per gene)...")
            else:
                self.logger.info(f"Applying adaptive MM0 threshold (min_MM0 to min_MM0+{mm0_tolerance} per gene)...")
        
        filtered = []
        
        for gene, group in df.groupby('Gene'):
            # Find minimum MM0 for this gene
            min_mm0 = group['MM0'].min()
            max_allowed_mm0 = min_mm0 + mm0_tolerance
            
            # Keep guides with MM0 in acceptable range
            gene_filtered = group[
                (group['MM0'] >= min_mm0) &
                (group['MM0'] <= max_allowed_mm0)
            ]
            filtered.append(gene_filtered)
            
            if self.logger:
                count_at_min = len(group[group['MM0'] == min_mm0])
                if mm0_tolerance == 0:
                    self.logger.info(f"  {gene}: MM0 = {min_mm0} ({len(gene_filtered)} guides)")
                else:
                    self.logger.info(f"  {gene}: MM0 range {min_mm0}-{max_allowed_mm0} "
                                   f"({count_at_min} at min, {len(gene_filtered)} in range)")
        
        result = pd.concat(filtered, ignore_index=True)
        
        if self.logger:
            self.logger.info(f"After adaptive MM0 filtering: {len(result)} guides")
        
        return result
    
    def _print_summary(self, df):
        """Print summary statistics"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Summary Statistics")
        self.logger.info("=" * 60)
        
        self.logger.info(f"\nGuide Score Statistics:")
        self.logger.info(f"  Min:    {df['Score'].min():.5f}")
        self.logger.info(f"  Max:    {df['Score'].max():.5f}")
        self.logger.info(f"  Mean:   {df['Score'].mean():.5f}")
        self.logger.info(f"  Median: {df['Score'].median():.5f}")
        
        self.logger.info(f"\nOff-target Statistics:")
        for mm in ['MM0', 'MM1', 'MM2']:
            if mm in df.columns:
                self.logger.info(f"  {mm}: min={df[mm].min():.0f}, median={df[mm].median():.0f}, max={df[mm].max():.0f}")
        
        self.logger.info(f"\nGuides per gene:")
        for gene in sorted(df['Gene'].unique()):
            gene_guides = df[df['Gene'] == gene]
            min_score = gene_guides['Score'].min()
            max_score = gene_guides['Score'].max()
            min_mm0 = gene_guides['MM0'].min()
            self.logger.info(f"  {gene:<15} {len(gene_guides):2} guides  "
                           f"Score: {min_score:.3f}-{max_score:.3f}  MM0: {min_mm0:.0f}")
    
    def _step_validate_mm0(self, final_guides_file):
        """Step 5 (Optional): Validate MM0 locations"""
        if self.logger:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("STEP 5: Validate MM0 Locations (Optional)")
            self.logger.info("=" * 60)
        
        try:
            # Import validation module
            from tiger.validation import validate_final_guides
            
            # Get reference transcriptome path
            offtarget_config = self.config['offtarget']
            transcriptome_path = Path(offtarget_config['reference_transcriptome'])
            
            if not transcriptome_path.exists():
                if self.logger:
                    self.logger.warning(f"Transcriptome file not found: {transcriptome_path}")
                    self.logger.warning("Skipping MM0 location validation")
                return
            
            # Need to find the FASTA version (not joined)
            # Try common locations
            fasta_path = transcriptome_path.parent / 'gencode.vM37.transcripts.fa'
            if not fasta_path.exists():
                # Try to infer from config
                if self.logger:
                    self.logger.warning(f"FASTA transcriptome not found: {fasta_path}")
                    self.logger.warning("Skipping MM0 location validation")
                return
            
            # Output path
            output_file = self.output_dir / 'mm0_location_analysis.csv'
            
            # Run validation
            results_df, stats = validate_final_guides(
                guides_csv=str(final_guides_file),
                transcriptome_file=str(fasta_path),
                output_file=str(output_file),
                logger=self.logger
            )
            
            if self.logger:
                self.logger.info(f"✅ MM0 validation complete: {output_file}")
        
        except ImportError as e:
            if self.logger:
                self.logger.warning(f"Could not import validation module: {e}")
                self.logger.warning("Skipping MM0 location validation")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"MM0 validation failed: {e}")
                self.logger.warning("Continuing without validation")
    
    def _print_workflow_plan(self):
        """Print workflow execution plan (dry run)"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("WORKFLOW EXECUTION PLAN (DRY RUN)")
        self.logger.info("=" * 60)
        
        self.logger.info("\n1. Download FASTA sequences")
        self.logger.info(f"   - Species: {self.config['species']}")
        self.logger.info(f"   - Genes: {len(self.targets)}")
        self.logger.info(f"   - Output: {self.output_dir}/sequences/")
        
        self.logger.info("\n2. Run TIGER prediction")
        self.logger.info(f"   - Model: {self.config['tiger']['model_path']}")
        self.logger.info(f"   - Guide length: {self.config['tiger']['guide_length']}")
        self.logger.info(f"   - Output: {self.output_dir}/tiger/")
        
        self.logger.info("\n3. Off-target analysis")
        self.logger.info(f"   - Reference: {self.config['offtarget']['reference_transcriptome']}")
        self.logger.info(f"   - Max mismatches: {self.config['offtarget']['max_mismatches']}")
        self.logger.info(f"   - Output: {self.output_dir}/offtarget/")
        
        self.logger.info("\n4. Filter and rank guides")
        self.logger.info(f"   - Top N per gene: {self.config['top_n_guides']}")
        self.logger.info(f"   - MM1 threshold: {self.config['filtering']['mm1_threshold']}")
        self.logger.info(f"   - MM2 threshold: {self.config['filtering']['mm2_threshold']}")
        self.logger.info(f"   - Output: {self.output_dir}/final_guides.csv")
