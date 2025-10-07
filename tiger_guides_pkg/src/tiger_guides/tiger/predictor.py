"""TIGER wrapper for Cas13 guide prediction."""
from pathlib import Path
import pandas as pd
import numpy as np
from Bio import SeqIO

try:
    import tensorflow as tf
except ModuleNotFoundError as exc:  # pragma: no cover - import-time guard
    raise ModuleNotFoundError(
        "TensorFlow is required to run TIGER predictions. "
        "Install an appropriate TensorFlow build (e.g. 'pip install tensorflow-cpu>=2.18,<2.21' on Linux "
        "or 'pip install tensorflow-macos' on Apple Silicon)."
    ) from exc

from ..tiger_core import tiger as tiger_module

class TIGERPredictor:
    """Wrapper for TIGER Cas13 guide prediction"""
    
    def __init__(self, model_path, config, logger=None):
        """
        Initialize TIGER predictor

        Args:
            model_path: Path to TIGER model directory
            config: Configuration dictionary
            logger: Optional logger
        """
        self.model_path = Path(model_path)
        self.config = config
        self.logger = logger
        self.model = None
        self._is_savedmodel = False

        # Import TIGER modules
        self._import_tiger()
    
    def _import_tiger(self):
        """Import TIGER modules from local installation"""
        try:
            if self.logger:
                tiger_core_path = Path(__file__).parent.parent / 'tiger_core'
                self.logger.info(f"✅ Loaded TIGER from local installation: {tiger_core_path}")
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to import TIGER: {e}")
            raise
    
    def load_model(self):
        """Load TIGER model"""
        if self.logger:
            self.logger.info(f"Loading TIGER model from {self.model_path}...")

        try:
            # Load the TensorFlow SavedModel
            model_dir = self.model_path / 'model'
            if not model_dir.exists():
                raise FileNotFoundError(f"Model directory not found: {model_dir}")

            # Use TF SavedModel loader for compatibility with Keras 3
            try:
                # First try the new Keras 3 method
                self.model = tf.keras.models.load_model(str(model_dir), compile=False)
            except (ValueError, OSError):
                # Fall back to loading as TensorFlow SavedModel
                if self.logger:
                    self.logger.info("Using TF SavedModel loader (Keras 3 compatibility mode)")
                loaded = tf.saved_model.load(str(model_dir))
                # Get the inference function
                self.model = loaded.signatures['serving_default']
                self._is_savedmodel = True
            else:
                self._is_savedmodel = False

            # Load calibration and scoring parameters
            self.calibration_params = pd.read_pickle(str(self.model_path / 'calibration_params.pkl'))
            self.scoring_params = pd.read_pickle(str(self.model_path / 'scoring_params.pkl'))

            if self.logger:
                self.logger.info("✅ TIGER model loaded")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load TIGER model: {e}")
            raise
    
    def predict_from_fasta(self, fasta_path, output_path=None, batch_size=500):
        """
        Predict guide scores from FASTA file
        
        Args:
            fasta_path: Path to input FASTA file
            output_path: Path to output CSV file
            batch_size: Batch size for prediction
            
        Returns:
            pd.DataFrame: Predictions
        """
        if self.model is None:
            self.load_model()
        
        if self.logger:
            self.logger.info(f"Predicting guides from {fasta_path}...")
        
        # Read FASTA
        records = list(SeqIO.parse(fasta_path, 'fasta'))
        
        if self.logger:
            self.logger.info(f"Processing {len(records)} sequences...")
        
        # Generate guides and predict scores
        all_predictions = []
        
        for i, record in enumerate(records):
            if self.logger and (i + 1) % 10 == 0:
                self.logger.info(f"Processed {i + 1}/{len(records)} sequences...")
            
            try:
                # Extract gene name from record ID
                gene_name = record.id.split('_')[0]
                
                # Generate guides from sequence
                guides = self._generate_guides(str(record.seq), gene_name)
                
                if guides:
                    all_predictions.extend(guides)
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error processing {record.id}: {e}")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_predictions)
        
        # Save output
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            
            if self.logger:
                self.logger.info(f"💾 Saved {len(df)} guides to {output_path}")
        
        return df
    
    def _generate_guides(self, sequence, gene_name):
        """
        Generate all possible guides from a sequence
        
        Args:
            sequence: Nucleotide sequence
            gene_name: Gene name
            
        Returns:
            list: List of guide dictionaries
        """
        guide_length = self.config.get('guide_length', 23)
        context_5p = self.config.get('context_5p', 3)
        context_3p = self.config.get('context_3p', 0)
        
        # Use TIGER's process_data function to get all guides
        target_seq, guide_seq, model_inputs = tiger_module.process_data(sequence.upper())

        if len(target_seq) == 0:
            if self.logger:
                self.logger.warning(f"{gene_name}: sequence shorter than target length - no guides generated")
            return []

        input_tensor = tf.cast(model_inputs, tf.float32)

        # Get predictions from the model
        if self._is_savedmodel:
            predictions = self.model(sequence_sequential_with_non_sequence_bypass_input=input_tensor)
            if isinstance(predictions, dict):
                lfc_estimate = predictions['dense_2'].numpy().reshape(-1)
            else:
                lfc_estimate = predictions.numpy().reshape(-1)
        else:
            lfc_estimate = self.model.predict(input_tensor, batch_size=500, verbose=False).reshape(-1)

        if lfc_estimate.size == 0:
            return []

        # Calibrate and score predictions
        lfc_estimate = tiger_module.calibrate_predictions(
            lfc_estimate,
            num_mismatches=np.zeros_like(lfc_estimate),
            params=self.calibration_params
        )
        scores = tiger_module.score_predictions(lfc_estimate, params=self.scoring_params)
        
        # Build guide list
        guides = []
        for i, (target, guide, score) in enumerate(zip(target_seq, guide_seq, scores)):
            guides.append({
                'Gene': gene_name,
                'Position': i,
                'Sequence': guide[::-1],  # Reverse guide sequence (TIGER reverses it)
                'Score': round(float(score), 5),
                'Target': target[context_5p:len(target) - context_3p] if context_3p > 0 else target[context_5p:]
            })
        
        return guides
