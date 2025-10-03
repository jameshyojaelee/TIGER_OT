"""
Download sequences from Ensembl REST API
"""
import requests
import time
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

class EnsemblDownloader:
    """Download sequences from Ensembl REST API"""
    
    def __init__(self, species='mus_musculus', rest_url='https://rest.ensembl.org',
                 rate_limit_delay=0.5, logger=None):
        """
        Initialize Ensembl downloader
        
        Args:
            species: Species name (e.g., 'mus_musculus', 'homo_sapiens')
            rest_url: Ensembl REST API URL
            rate_limit_delay: Delay between requests (seconds)
            logger: Optional logger
        """
        self.species = species
        self.rest_url = rest_url.rstrip('/')
        self.rate_limit_delay = rate_limit_delay
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def get_gene_id(self, gene_name):
        """
        Get Ensembl gene ID from gene symbol
        
        Args:
            gene_name: Gene symbol (e.g., 'Nanog')
            
        Returns:
            str: Ensembl gene ID or None
        """
        url = f"{self.rest_url}/lookup/symbol/{self.species}/{gene_name}"
        
        try:
            response = self.session.get(url)
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('id')
            else:
                if self.logger:
                    self.logger.warning(f"Gene {gene_name} not found (HTTP {response.status_code})")
                return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error fetching gene ID for {gene_name}: {e}")
            return None
    
    def get_transcripts(self, gene_id):
        """
        Get all transcripts for a gene
        
        Args:
            gene_id: Ensembl gene ID
            
        Returns:
            list: List of transcript dictionaries
        """
        url = f"{self.rest_url}/lookup/id/{gene_id}?expand=1"
        
        try:
            response = self.session.get(url)
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('Transcript', [])
            else:
                if self.logger:
                    self.logger.warning(f"No transcripts found for {gene_id}")
                return []
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error fetching transcripts for {gene_id}: {e}")
            return []
    
    def select_best_transcript(self, transcripts):
        """
        Select the best transcript (canonical or APPRIS principal)
        
        Args:
            transcripts: List of transcript dictionaries
            
        Returns:
            dict: Best transcript or None
        """
        if not transcripts:
            return None
        
        # Prefer canonical transcript
        for transcript in transcripts:
            if transcript.get('is_canonical'):
                return transcript
        
        # Fallback: return first transcript
        return transcripts[0]
    
    def get_sequence(self, transcript_id, seq_type='cds'):
        """
        Get sequence for a transcript
        
        Args:
            transcript_id: Ensembl transcript ID
            seq_type: Sequence type ('cds', 'cdna', 'protein')
            
        Returns:
            str: Sequence or None
        """
        url = f"{self.rest_url}/sequence/id/{transcript_id}?type={seq_type}"
        
        try:
            response = self.session.get(url)
            time.sleep(self.rate_limit_delay)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('seq')
            else:
                if self.logger:
                    self.logger.warning(f"No {seq_type} sequence for {transcript_id}")
                return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error fetching sequence for {transcript_id}: {e}")
            return None
    
    def download_gene(self, gene_name, seq_type='cds', output_dir=None):
        """
        Download best transcript sequence for a gene
        
        Args:
            gene_name: Gene symbol
            seq_type: Sequence type ('cds', 'cdna', 'protein')
            output_dir: Optional output directory for individual FASTA files
            
        Returns:
            SeqRecord or None
        """
        if self.logger:
            self.logger.info(f"Downloading {gene_name}...")
        
        # Get gene ID
        gene_id = self.get_gene_id(gene_name)
        if not gene_id:
            return None
        
        # Get transcripts
        transcripts = self.get_transcripts(gene_id)
        if not transcripts:
            return None
        
        # Select best transcript
        best_transcript = self.select_best_transcript(transcripts)
        if not best_transcript:
            return None
        
        transcript_id = best_transcript['id']
        
        # Get sequence
        sequence = self.get_sequence(transcript_id, seq_type)
        if not sequence:
            return None
        
        # Create SeqRecord
        record = SeqRecord(
            Seq(sequence.upper()),
            id=f"{gene_name}_{transcript_id}",
            description=f"{gene_name} | {transcript_id} | {seq_type}"
        )
        
        # Save individual FASTA if requested
        if output_dir:
            output_path = Path(output_dir) / f"{gene_name}_{seq_type}.fasta"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            SeqIO.write([record], output_path, 'fasta')
        
        return record
    
    def download_genes(self, gene_list, seq_type='cds', output_fasta=None, 
                      output_dir=None):
        """
        Download sequences for multiple genes
        
        Args:
            gene_list: List of gene names
            seq_type: Sequence type ('cds', 'cdna', 'protein')
            output_fasta: Path to merged output FASTA file
            output_dir: Directory for individual FASTA files
            
        Returns:
            list: List of SeqRecords
        """
        records = []
        
        for gene_name in gene_list:
            record = self.download_gene(gene_name, seq_type, output_dir)
            if record:
                records.append(record)
                if self.logger:
                    self.logger.info(f"✅ {gene_name}: {len(record.seq)} bp")
            else:
                if self.logger:
                    self.logger.error(f"❌ {gene_name}: Failed to download")
        
        # Save merged FASTA
        if output_fasta and records:
            output_path = Path(output_fasta)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            SeqIO.write(records, output_path, 'fasta')
            
            if self.logger:
                self.logger.info(f"💾 Saved {len(records)} sequences to {output_fasta}")
        
        return records
