"""
Configuration for BioDiscovery AI
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Dict, Any, List, Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # App info
    APP_NAME: str = "BioDiscovery AI"
    APP_VERSION: str = "1.0.0"
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: Optional[str] = None
    
    # Gemini - Use a valid model name
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"  # Valid model
    
    # App
    debug: bool = False
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in .env


# Collection configurations
COLLECTION_CONFIGS: Dict[str, Dict[str, Any]] = {
    "proteins": {
        "vectors": {
            "text": 768,      # BGE-base
            "sequence": 320,  # ESM-2
        },
        "sparse_vectors": ["text_sparse"],
        "payload_indexes": ["gene_names", "organism", "diseases"],
        "primary_for": ["sequence", "text_sequence"],
    },
    "articles": {
        "vectors": {
            "text": 768,
        },
        "sparse_vectors": ["text_sparse"],
        "payload_indexes": ["pmid", "year", "journal"],
        "primary_for": ["text"],
    },
    "images": {
        "vectors": {
            "image": 512,    # CLIP
            "caption": 768,  # BGE for caption text
        },
        "sparse_vectors": ["caption_sparse"],
        "payload_indexes": ["source", "image_type", "gene_name"],
        "primary_for": ["image", "text_image"],
    },
    "experiments": {
        "vectors": {
            "text": 768,
        },
        "sparse_vectors": ["text_sparse"],
        "payload_indexes": ["accession", "data_type", "organism"],
        "primary_for": [],
    },
    "structures": {
        "vectors": {
            "text": 768,
            "structure": 768,  # Structure-specific vector (from PDB text/sequence)
        },
        "sparse_vectors": ["text_sparse"],
        "payload_indexes": ["pdb_id", "method", "resolution"],
        "primary_for": ["structure", "text_structure"],
    },
}

# Input type to primary collection mapping
INPUT_TYPE_TO_COLLECTION: Dict[str, str] = {
    "text": "articles",
    "sequence": "proteins",
    "image": "images",
    "structure": "structures",
    "text_sequence": "proteins",
    "text_image": "images",
    "text_structure": "structures",
}

# Vector name mapping by input type
INPUT_TYPE_TO_VECTOR: Dict[str, str] = {
    "text": "text",
    "sequence": "sequence",
    "image": "image",
    "structure": "text",
    "text_sequence": "text",
    "text_image": "caption",
    "text_structure": "text",
}


@lru_cache()
def get_settings() -> Settings:
    return Settings()