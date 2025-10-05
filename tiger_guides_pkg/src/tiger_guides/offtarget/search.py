"""
Python wrapper for C off-target search
"""
import subprocess
import pandas as pd
from pathlib import Path
import tempfile
import shutil

class OffTargetSearcher:
    """Wrapper for C off-target search binary"""
    
    def __init__(self, binary_path, reference_path, logger=None):
        """
        Initialize off-target searcher
        
        Args:
            binary_path: Path to compiled C binary
            reference_path: Path to reference transcriptome
            logger: Optional logger
        """
        self.binary_path = Path(binary_path)
        self.reference_path = Path(reference_path)
        self.logger = logger
        
        # Check if binary exists
        if not self.binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {self.binary_path}")
        
        # Check if reference exists
        if not self.reference_path.exists():
            raise FileNotFoundError(f"Reference not found: {self.reference_path}")
    
    def search(self, guides_df, output_path=None, chunk_size=None):
        """
        Search for off-targets
        
        Args:
            guides_df: DataFrame with guides (columns: Gene, Sequence, Score, ...)
            output_path: Path to save results
            chunk_size: If specified, process in chunks
            
        Returns:
            pd.DataFrame: Results with off-target counts
        """
        if self.logger:
            self.logger.info(f"Searching off-targets for {len(guides_df)} guides...")
        
        if chunk_size and len(guides_df) > chunk_size:
            # Process in chunks
            results = []
            for i in range(0, len(guides_df), chunk_size):
                chunk = guides_df.iloc[i:i+chunk_size]
                if self.logger:
                    self.logger.info(f"Processing chunk {i//chunk_size + 1}/{(len(guides_df)-1)//chunk_size + 1}...")
                result = self._search_chunk(chunk)
                results.append(result)
            
            final_result = pd.concat(results, ignore_index=True)
        else:
            # Process all at once
            final_result = self._search_chunk(guides_df)
        
        # Save results
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_result.to_csv(output_path, index=False)
            
            if self.logger:
                self.logger.info(f"💾 Saved results to {output_path}")
        
        return final_result
    
    def _search_chunk(self, guides_df):
        """
        Search a chunk of guides
        
        Args:
            guides_df: DataFrame with guides
            
        Returns:
            pd.DataFrame: Results
        """
        # Create temporary input file
        search_col = 'Target' if 'Target' in guides_df.columns else 'Sequence'
        export_df = guides_df[['Gene', search_col]].rename(columns={search_col: 'Sequence'})

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_in:
            export_df.to_csv(tmp_in.name, index=False)
            tmp_input = tmp_in.name

        # Create temporary output file
        tmp_output = tempfile.mktemp(suffix='.csv')

        try:
            # Run C binary
            cmd = [
                str(self.binary_path),
                tmp_input,
                str(self.reference_path),
                tmp_output
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if self.logger and result.stderr:
                # Log stderr (progress messages)
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.logger.debug(line.strip())

            # Read results
            results_df = pd.read_csv(tmp_output)
            if search_col == 'Target':
                results_df = results_df.rename(columns={'Sequence': 'Target'})

            # Merge with original guide data
            merged = guides_df.merge(
                results_df,
                on=['Gene', search_col],
                how='left'
            )

            return merged
        
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.error(f"Off-target search failed: {e}")
                self.logger.error(f"stderr: {e.stderr}")
            raise
        
        finally:
            # Clean up temporary files
            Path(tmp_input).unlink(missing_ok=True)
            Path(tmp_output).unlink(missing_ok=True)
    
    def search_parallel_slurm(self, guides_df, output_dir, chunk_size=1500, 
                             slurm_config=None):
        """
        Search for off-targets using SLURM array jobs
        
        Args:
            guides_df: DataFrame with guides
            output_dir: Output directory for results
            chunk_size: Guides per SLURM job
            slurm_config: SLURM configuration dict
            
        Returns:
            list: List of SLURM job IDs
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Split guides into chunks
        n_chunks = (len(guides_df) - 1) // chunk_size + 1
        
        if self.logger:
            self.logger.info(f"Splitting {len(guides_df)} guides into {n_chunks} chunks...")
        
        # Save chunks
        chunk_dir = output_dir / 'chunks'
        chunk_dir.mkdir(exist_ok=True)
        
        for i in range(n_chunks):
            chunk = guides_df.iloc[i*chunk_size:(i+1)*chunk_size]
            chunk_file = chunk_dir / f'chunk_{i:04d}.csv'
            chunk.to_csv(chunk_file, index=False)
        
        # Create SLURM script
        slurm_script = self._create_slurm_script(
            output_dir, n_chunks, slurm_config
        )
        
        # Submit SLURM job
        from ..slurm import submit_slurm_job
        
        job_id = submit_slurm_job(
            slurm_script,
            job_name='offtarget',
            **slurm_config
        )
        
        if self.logger:
            self.logger.info(f"Submitted SLURM array job: {job_id}")
        
        return [job_id]
    
    def _create_slurm_script(self, output_dir, n_chunks, slurm_config):
        """Create SLURM array job script"""
        script_path = output_dir / 'run_offtarget.sh'
        
        with open(script_path, 'w') as f:
            f.write(f"""#!/bin/bash
#SBATCH --account={slurm_config.get('account', 'sanjana')}
#SBATCH --partition={slurm_config.get('partition', 'cpu')}
#SBATCH --time={slurm_config.get('time', '02:00:00')}
#SBATCH --mem={slurm_config.get('mem', '8G')}
#SBATCH --cpus-per-task={slurm_config.get('cpus_per_task', 1)}
#SBATCH --array=0-{n_chunks-1}
#SBATCH --output={output_dir}/logs/offtarget_%a.out
#SBATCH --error={output_dir}/logs/offtarget_%a.err

# Create logs directory
mkdir -p {output_dir}/logs

# Run off-target search
{self.binary_path} \\
    {output_dir}/chunks/chunk_$(printf "%04d" $SLURM_ARRAY_TASK_ID).csv \\
    {self.reference_path} \\
    {output_dir}/results/result_$(printf "%04d" $SLURM_ARRAY_TASK_ID).csv
""")
        
        script_path.chmod(0o755)
        return script_path
