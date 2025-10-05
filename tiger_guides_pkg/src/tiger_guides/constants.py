"""Shared constants for the tiger_guides package."""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_ROOT / "data"
SMOKE_DIR = DATA_DIR / "smoke"

DEFAULT_ENS_URL = "https://rest.ensembl.org"
DEFAULT_RATE_LIMIT = 0.5

SPECIES_CATALOG = {
    "mouse": {
        "ensembl_name": "mus_musculus",
        "reference_filename": "gencode.vM37.transcripts.uc.joined",
        "reference_url": "https://ftp.ensembl.org/pub/release-110/fasta/mus_musculus/cdna/Mus_musculus.GRCm39.cdna.all.fa.gz",
        "reference_md5": "3b14f3fa2d5c7334e0fdd03f5c12d33b",
    },
    "human": {
        "ensembl_name": "homo_sapiens",
        "reference_filename": "gencode.v47.transcripts.fa",
        "reference_url": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_47/gencode.v47.transcripts.fa.gz",
        "reference_md5": "4d5aed375b2dd54fca86e9e74cc9ae65",
    },
}

MODEL_CATALOG = {
    "tiger": {
        "target_dir": "resources/models/tiger_model",
        "archive_env": "TIGER_MODEL_ARCHIVE",
        "url_env": "TIGER_MODEL_ARCHIVE_URL",
        "md5_env": "TIGER_MODEL_ARCHIVE_MD5",
        "required_files": [
            "model/saved_model.pb",
            "model/variables/variables.data-00000-of-00001",
            "model/variables/variables.index",
            "calibration_params.pkl",
            "scoring_params.pkl",
        ],
    }
}
