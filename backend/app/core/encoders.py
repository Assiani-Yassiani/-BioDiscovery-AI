"""
Multi-modal encoders for BioDiscovery AI
Optimized for SCIENTIFIC/BIOMEDICAL data with best free models (2024-2025)

Models used:
- Text: PubMedBERT (Microsoft) - Trained on 30M+ PubMed articles
- Images: BiomedCLIP (Microsoft) - Trained on biomedical images
- Sequences: ESM-2 650M (Meta) - State-of-the-art protein language model
- Structures: Hybrid (sequence + geometry + text)
"""

import numpy as np
from typing import List, Optional, Union, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# TEXT ENCODER - PubMedBERT (Specialized for biomedical text)
# =============================================================================


class TextEncoder:
    """
    Text encoder using Gemini API embeddings

    Why Gemini embeddings:
    - Works on Windows without PyTorch DLL issues
    - High quality embeddings (768 dimensions)
    - Free tier available
    - Fast API calls

    Model: models/embedding-001
    Dimensions: 768
    """

    _instance = None
    _configured = False
    _use_gemini = False
    _model = None
    _model_type = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if TextEncoder._model is None and not TextEncoder._configured:
            self._load_model()

    def _load_model(self):
        """Load embedding model - tries Gemini first, then local models"""

        # Try Gemini API first (works on Windows!)
        try:
            import google.generativeai as genai
            from app.config import get_settings

            settings = get_settings()
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
                # Test the connection
                test_result = genai.embed_content(
                    model="models/embedding-001",
                    content="test",
                    task_type="retrieval_document",
                )
                if test_result and "embedding" in test_result:
                    TextEncoder._configured = True
                    TextEncoder._use_gemini = True
                    TextEncoder._model_type = "gemini"
                    logger.info(
                        "✅ Gemini embeddings configured successfully (768 dims)"
                    )
                    return
        except Exception as e:
            logger.warning(f"Gemini embeddings failed: {e}")

        # Fallback to local models
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading fallback: BAAI/bge-base-en-v1.5")
            TextEncoder._model = SentenceTransformer("BAAI/bge-base-en-v1.5")
            TextEncoder._model_type = "bge"
            TextEncoder._configured = True
            logger.info("✅ BGE encoder loaded (local fallback)")
            return
        except Exception as e2:
            logger.warning(f"BGE also failed: {e2}")

        # Try PubMedBERT
        try:
            from transformers import AutoTokenizer, AutoModel

            model_name = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"
            TextEncoder._tokenizer = AutoTokenizer.from_pretrained(model_name)
            TextEncoder._model = AutoModel.from_pretrained(model_name)
            TextEncoder._model.eval()
            TextEncoder._model_type = "pubmedbert"
            TextEncoder._configured = True
            logger.info("✅ PubMedBERT loaded successfully")
            return
        except Exception as e3:
            logger.warning(f"PubMedBERT also failed: {e3}")

        logger.error("❌ No text encoder available - using random vectors")
        TextEncoder._configured = False

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Encode text(s) to vectors"""
        if isinstance(texts, str):
            texts = [texts]

        # Use Gemini API
        if TextEncoder._use_gemini:
            return self._encode_gemini(texts)

        # Use local BGE model
        if TextEncoder._model_type == "bge" and TextEncoder._model is not None:
            vectors = TextEncoder._model.encode(texts, normalize_embeddings=True)
            return np.array(vectors, dtype=np.float32)

        # Use PubMedBERT
        if TextEncoder._model_type == "pubmedbert" and TextEncoder._model is not None:
            return self._encode_pubmedbert(texts)

        # Fallback to random vectors
        logger.warning("Using random vectors (no model loaded)")
        return np.random.randn(len(texts), 768).astype(np.float32)

    def _encode_gemini(self, texts: List[str]) -> np.ndarray:
        """Encode using Gemini API"""
        import google.generativeai as genai

        vectors = []
        for text in texts:
            try:
                # Truncate if too long (Gemini limit)
                text = text[:2000] if len(text) > 2000 else text

                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document",
                )
                embedding = np.array(result["embedding"], dtype=np.float32)
                # Normalize
                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
                vectors.append(embedding)
            except Exception as e:
                logger.error(f"Gemini embedding error: {e}")
                vectors.append(np.random.randn(768).astype(np.float32))

        return np.array(vectors, dtype=np.float32)

    def _encode_pubmedbert(self, texts: List[str]) -> np.ndarray:
        """Encode using PubMedBERT"""
        import torch

        vectors = []
        for text in texts:
            inputs = TextEncoder._tokenizer(
                text, return_tensors="pt", truncation=True, max_length=512, padding=True
            )

            with torch.no_grad():
                outputs = TextEncoder._model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
                vectors.append(embedding)

        return np.array(vectors, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return 768


# =============================================================================
# IMAGE ENCODER - BiomedCLIP (Specialized for biomedical images)
# =============================================================================


class ImageEncoder:
    """
    Image encoder using BiomedCLIP - specialized for biomedical images

    Why BiomedCLIP is better than standard CLIP:
    - Trained on PMC-15M (15 million biomedical image-text pairs)
    - Understands: X-rays, microscopy, pathology, pathway diagrams
    - +15-25% better on medical image tasks vs CLIP

    Model: microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224
    Dimensions: 512
    """

    _instance = None
    _model = None
    _processor = None
    _model_type = None  # 'biomedclip', 'clip', or None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ImageEncoder._model is None:
            self._load_model()

    def _load_model(self):
        """Load BiomedCLIP model"""
        # Try BiomedCLIP first
        try:
            from open_clip import create_model_from_pretrained, get_tokenizer
            import torch

            logger.info("Loading image encoder: BiomedCLIP")
            model, preprocess = create_model_from_pretrained(
                "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"
            )
            ImageEncoder._model = model
            ImageEncoder._processor = preprocess
            ImageEncoder._model_type = "biomedclip"
            ImageEncoder._model.eval()

            logger.info("✅ BiomedCLIP loaded successfully (biomedical-specialized)")
            return
        except Exception as e:
            logger.warning(f"BiomedCLIP failed: {e}")

        # Fallback to standard CLIP via sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading fallback: clip-ViT-B-32")
            ImageEncoder._model = SentenceTransformer("clip-ViT-B-32")
            ImageEncoder._model_type = "clip"
            logger.info("✅ CLIP encoder loaded (general-purpose fallback)")
            return
        except Exception as e2:
            logger.warning(f"CLIP also failed: {e2}. Using random vectors.")

        ImageEncoder._model = None
        ImageEncoder._model_type = None

    def encode(
        self, image_paths: Union[str, Path, List[Union[str, Path]]]
    ) -> np.ndarray:
        """Encode image(s) to vectors"""
        if isinstance(image_paths, (str, Path)):
            image_paths = [image_paths]

        if ImageEncoder._model is None:
            logger.warning("Using random vectors (no model loaded)")
            return np.random.randn(len(image_paths), 512).astype(np.float32)

        from PIL import Image

        if ImageEncoder._model_type == "clip":
            try:
                images = [Image.open(p).convert("RGB") for p in image_paths]
                vectors = ImageEncoder._model.encode(images, normalize_embeddings=True)
                return np.array(vectors, dtype=np.float32)
            except Exception as e:
                logger.error(f"Error encoding images: {e}")
                return np.random.randn(len(image_paths), 512).astype(np.float32)

        # Using BiomedCLIP
        import torch

        vectors = []
        for img_path in image_paths:
            try:
                image = Image.open(img_path).convert("RGB")
                image_input = ImageEncoder._processor(image).unsqueeze(0)

                with torch.no_grad():
                    image_features = ImageEncoder._model.encode_image(image_input)
                    embedding = image_features.squeeze().numpy()
                    embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
                    vectors.append(embedding)
            except Exception as e:
                logger.error(f"Error encoding image {img_path}: {e}")
                vectors.append(np.random.randn(512).astype(np.float32))

        return np.array(vectors, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return 512


# =============================================================================
# SEQUENCE ENCODER - ESM-2 (State-of-the-art protein language model)
# =============================================================================


class SequenceEncoder:
    """
    Protein sequence encoder using ESM-2 - Meta's protein language model

    Why ESM-2 is the best:
    - Trained on 250M protein sequences
    - State-of-the-art on protein benchmarks
    - Captures evolutionary and structural information

    Model: facebook/esm2_t33_650M_UR50D (650M params)
    Fallback: facebook/esm2_t6_8M_UR50D (8M params - lighter)

    Dimensions: 320 (reduced for compatibility)
    """

    _instance = None
    _model = None
    _tokenizer = None
    _use_esm = False
    _output_dim = 320

    AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"

    # Physicochemical properties
    HYDROPHOBICITY = {
        "A": 1.8,
        "C": 2.5,
        "D": -3.5,
        "E": -3.5,
        "F": 2.8,
        "G": -0.4,
        "H": -3.2,
        "I": 4.5,
        "K": -3.9,
        "L": 3.8,
        "M": 1.9,
        "N": -3.5,
        "P": -1.6,
        "Q": -3.5,
        "R": -4.5,
        "S": -0.8,
        "T": -0.7,
        "V": 4.2,
        "W": -0.9,
        "Y": -1.3,
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SequenceEncoder._model is None:
            self._load_model()

    def _load_model(self):
        """Load ESM-2 model"""
        # Try larger ESM-2 first
        for model_name in ["facebook/esm2_t33_650M_UR50D", "facebook/esm2_t6_8M_UR50D"]:
            try:
                import torch
                from transformers import AutoTokenizer, AutoModel

                logger.info(f"Loading sequence encoder: {model_name}")

                SequenceEncoder._tokenizer = AutoTokenizer.from_pretrained(model_name)
                SequenceEncoder._model = AutoModel.from_pretrained(model_name)
                SequenceEncoder._model.eval()
                SequenceEncoder._use_esm = True

                logger.info(f"✅ {model_name} loaded successfully")
                return

            except Exception as e:
                logger.warning(f"{model_name} failed: {e}")

        logger.warning("All ESM models failed. Using AA composition fallback.")
        SequenceEncoder._use_esm = False

    def encode(self, sequences: Union[str, List[str]]) -> np.ndarray:
        """Encode protein sequence(s) to vectors"""
        if isinstance(sequences, str):
            sequences = [sequences]

        if SequenceEncoder._use_esm and SequenceEncoder._model is not None:
            return self._encode_esm(sequences)
        else:
            return self._encode_aa_composition(sequences)

    def _encode_esm(self, sequences: List[str]) -> np.ndarray:
        """Encode using ESM-2 model"""
        import torch

        vectors = []
        for seq in sequences:
            seq = "".join(c for c in seq.upper() if c in self.AMINO_ACIDS + "X")
            seq = seq[:1024]

            if len(seq) < 5:
                vectors.append(np.zeros(self._output_dim, dtype=np.float32))
                continue

            inputs = SequenceEncoder._tokenizer(
                seq, return_tensors="pt", padding=True, truncation=True, max_length=1024
            )

            with torch.no_grad():
                outputs = SequenceEncoder._model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

                # Reduce dimensions if needed
                if len(embedding) > self._output_dim:
                    step = len(embedding) // (self._output_dim - 10)
                    reduced = embedding[::step][: self._output_dim - 10]
                    stats = [
                        np.mean(embedding),
                        np.std(embedding),
                        np.min(embedding),
                        np.max(embedding),
                        np.median(embedding),
                    ]
                    reduced = np.concatenate([reduced, stats])
                    reduced = reduced[: self._output_dim]
                    if len(reduced) < self._output_dim:
                        reduced = np.pad(reduced, (0, self._output_dim - len(reduced)))
                    embedding = reduced

                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
                vectors.append(embedding)

        return np.array(vectors, dtype=np.float32)

    def _encode_aa_composition(self, sequences: List[str]) -> np.ndarray:
        """Fallback: Advanced amino acid composition encoding"""
        vectors = []

        for seq in sequences:
            seq = "".join(c for c in seq.upper() if c in self.AMINO_ACIDS + "X")
            length = max(len(seq), 1)

            features = []

            # AA frequencies (20 dims)
            aa_freq = np.array([seq.count(aa) / length for aa in self.AMINO_ACIDS])
            features.extend(aa_freq)

            # Dipeptide frequencies (50 dims)
            common_dipeptides = [
                "LL",
                "AA",
                "VV",
                "GG",
                "SS",
                "AL",
                "LA",
                "AV",
                "VA",
                "LV",
                "VL",
                "IL",
                "LI",
                "EE",
                "KK",
                "AG",
                "GA",
                "AS",
                "SA",
                "AT",
                "TA",
                "SG",
                "GS",
                "ST",
                "TS",
                "EK",
                "KE",
                "DE",
                "ED",
                "ER",
                "RE",
                "LK",
                "KL",
                "LE",
                "EL",
                "AE",
                "EA",
                "AR",
                "RA",
                "AD",
                "DA",
                "AN",
                "NA",
                "AQ",
                "QA",
                "GL",
                "LG",
                "GV",
                "VG",
                "GT",
            ]
            dipeptide_freq = np.array(
                [seq.count(dp) / max(length - 1, 1) for dp in common_dipeptides]
            )
            features.extend(dipeptide_freq)

            # Physicochemical properties (30 dims)
            hydro_values = [self.HYDROPHOBICITY.get(aa, 0) for aa in seq]
            if hydro_values:
                features.extend(
                    [
                        np.mean(hydro_values),
                        np.std(hydro_values),
                        np.min(hydro_values),
                        np.max(hydro_values),
                        np.sum(np.array(hydro_values) > 0) / length,
                    ]
                )
            else:
                features.extend([0] * 5)

            # Property groups
            hydrophobic = sum(seq.count(aa) for aa in "AILMFVPWY") / length
            polar = sum(seq.count(aa) for aa in "STNQ") / length
            positive = sum(seq.count(aa) for aa in "KRH") / length
            negative = sum(seq.count(aa) for aa in "DE") / length
            aromatic = sum(seq.count(aa) for aa in "FWY") / length
            small = sum(seq.count(aa) for aa in "AGST") / length

            features.extend([hydrophobic, polar, positive, negative, aromatic, small])
            features.extend([np.log1p(length), length / 1000])

            # Pad to output dimension
            features = np.array(features, dtype=np.float32)
            if len(features) < self._output_dim:
                features = np.pad(features, (0, self._output_dim - len(features)))
            else:
                features = features[: self._output_dim]

            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm

            vectors.append(features)

        return np.array(vectors, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return self._output_dim


# =============================================================================
# STRUCTURE ENCODER - Hybrid (Sequence + Geometry + Text)
# =============================================================================


class StructureEncoder:
    """
    Structure encoder using hybrid approach:
    - Sequence features from ESM-2 (320 dims)
    - Text description from PubMedBERT (256 dims)
    - 3D geometric features (192 dims)

    Total: 768 dimensions
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.sequence_encoder = SequenceEncoder()
        self.text_encoder = TextEncoder()

    def encode(self, pdb_paths: Union[str, Path, List[Union[str, Path]]]) -> np.ndarray:
        """Encode PDB structure(s) to vectors"""
        if isinstance(pdb_paths, (str, Path)):
            pdb_paths = [pdb_paths]

        vectors = []
        for pdb_path in pdb_paths:
            vec = self._encode_single(pdb_path)
            vectors.append(vec)

        return np.array(vectors, dtype=np.float32)

    def _encode_single(self, pdb_path: Union[str, Path]) -> np.ndarray:
        """Encode a single PDB file"""
        try:
            with open(pdb_path, "r") as f:
                pdb_content = f.read()

            sequence = self._extract_sequence(pdb_content)
            title = self._extract_field(pdb_content, "TITLE")
            method = self._extract_field(pdb_content, "EXPDTA")
            geo_features = self._extract_geometric_features(pdb_content)

            # Encode sequence (320 dims)
            if sequence and len(sequence) > 10:
                seq_vec = self.sequence_encoder.encode(sequence)[0]
            else:
                seq_vec = np.zeros(320, dtype=np.float32)

            # Encode text (768 -> 256 dims)
            text_desc = f"{title} {method} protein structure"
            full_text_vec = self.text_encoder.encode(text_desc)[0]
            text_vec = full_text_vec[:256]

            # Combine: 320 + 256 + 192 = 768
            combined = np.concatenate([seq_vec, text_vec, geo_features])

            norm = np.linalg.norm(combined)
            if norm > 0:
                combined = combined / norm

            return combined.astype(np.float32)

        except Exception as e:
            logger.error(f"Error encoding structure {pdb_path}: {e}")
            return np.zeros(768, dtype=np.float32)

    def _extract_sequence(self, pdb_content: str) -> str:
        """Extract amino acid sequence from ATOM records"""
        aa_map = {
            "ALA": "A",
            "CYS": "C",
            "ASP": "D",
            "GLU": "E",
            "PHE": "F",
            "GLY": "G",
            "HIS": "H",
            "ILE": "I",
            "LYS": "K",
            "LEU": "L",
            "MET": "M",
            "ASN": "N",
            "PRO": "P",
            "GLN": "Q",
            "ARG": "R",
            "SER": "S",
            "THR": "T",
            "VAL": "V",
            "TRP": "W",
            "TYR": "Y",
        }

        residues = {}
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and len(line) > 26:
                if line[12:16].strip() == "CA":
                    res_name = line[17:20].strip()
                    chain = line[21] if len(line) > 21 else "A"
                    try:
                        res_num = int(line[22:26].strip())
                        key = (chain, res_num)
                        if key not in residues:
                            residues[key] = aa_map.get(res_name, "X")
                    except ValueError:
                        continue

        sorted_keys = sorted(residues.keys())
        return "".join(residues[k] for k in sorted_keys)

    def _extract_field(self, pdb_content: str, field: str) -> str:
        """Extract a field from PDB header"""
        for line in pdb_content.split("\n"):
            if line.startswith(field):
                return line[10:].strip()
        return ""

    def _extract_geometric_features(self, pdb_content: str) -> np.ndarray:
        """Extract 192-dimensional geometric features"""
        coords = []

        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and len(line) > 54:
                if line[12:16].strip() == "CA":
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append([x, y, z])
                    except ValueError:
                        continue

        if len(coords) < 3:
            return np.zeros(192, dtype=np.float32)

        coords = np.array(coords)
        n_residues = len(coords)
        features = []

        # Bounding box
        bbox_min = coords.min(axis=0)
        bbox_max = coords.max(axis=0)
        bbox_size = bbox_max - bbox_min
        features.extend(bbox_size.tolist())
        features.append(np.prod(bbox_size))  # Volume
        features.append(n_residues)

        # Center of mass
        center = coords.mean(axis=0)
        features.extend(center.tolist())

        # Radius of gyration
        rg = np.sqrt(np.mean(np.sum((coords - center) ** 2, axis=1)))
        features.append(rg)

        # Distance statistics
        seq_dists = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        features.extend(
            [
                np.mean(seq_dists),
                np.std(seq_dists),
                np.min(seq_dists),
                np.max(seq_dists),
            ]
        )

        center_dists = np.linalg.norm(coords - center, axis=1)
        features.extend([np.mean(center_dists), np.std(center_dists)])

        # End-to-end distance
        features.append(np.linalg.norm(coords[-1] - coords[0]))

        # Contact density (sampled)
        n_sample = min(50, n_residues)
        sample_idx = np.linspace(0, n_residues - 1, n_sample, dtype=int)
        sampled = coords[sample_idx]

        if len(sampled) > 1:
            from scipy.spatial.distance import pdist

            pairwise = pdist(sampled)
            contacts_8 = (pairwise < 8.0).sum() / len(pairwise)
            features.append(contacts_8)
            features.extend([np.mean(pairwise), np.std(pairwise)])
        else:
            features.extend([0, 0, 0])

        # Pad to 192
        features = np.array(features[:192], dtype=np.float32)
        if len(features) < 192:
            features = np.pad(features, (0, 192 - len(features)))

        return features

    @property
    def dimension(self) -> int:
        return 768


# =============================================================================
# SPARSE ENCODER - BM25-style with Biological Vocabulary
# =============================================================================


class SparseEncoder:
    """
    BM25-style sparse encoder with biological vocabulary.

    Features:
    - Biological term matching (genes, diseases, pathways)
    - TF-IDF weighting with category boosting
    - Uses bio_vocabulary.json for domain-specific terms

    Output: {"indices": [...], "values": [...]}
    """

    _instance = None
    _vocabulary = None
    _term_to_idx = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        default_vocab_size: int = 30000,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        if SparseEncoder._vocabulary is None:
            self._default_vocab_size = default_vocab_size
            self.k1 = k1
            self.b = b
            self.avg_doc_len = 50.0

            # Category weights for biological terms
            self.category_weights = {
                "genes": 3.0,
                "diseases": 2.5,
                "pathways": 2.0,
                "processes": 1.8,
                "drugs": 2.0,
                "organisms": 1.5,
                "anatomy": 1.5,
                "techniques": 1.2,
            }

            self._load_vocabulary()

    def _load_vocabulary(self):
        """Load biological vocabulary from JSON file."""
        import json
        import os

        # Try multiple paths for vocabulary file
        possible_paths = [
            Path(__file__).parent.parent.parent / "data" / "bio_vocabulary.json",
            Path("data/bio_vocabulary.json"),
            Path("backend/data/bio_vocabulary.json"),
            Path("/home/claude/biodiscovery-ai/backend/data/bio_vocabulary.json"),
        ]

        vocab_path = None
        for p in possible_paths:
            if p.exists():
                vocab_path = p
                break

        SparseEncoder._vocabulary = {}
        SparseEncoder._term_to_idx = {}

        if vocab_path:
            try:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    raw_vocab = json.load(f)

                idx = 0

                # Check if vocab is nested by category or flat
                first_value = next(iter(raw_vocab.values()), {})
                is_nested = (
                    isinstance(first_value, dict) and "category" not in first_value
                )

                if is_nested:
                    # Format: {"genes": {"BRCA1": {...}, ...}, "diseases": {...}}
                    for category, terms_dict in raw_vocab.items():
                        if not isinstance(terms_dict, dict):
                            continue
                        for term, info in terms_dict.items():
                            term_lower = term.lower()
                            weight = info.get("weight", 1.0)
                            aliases = info.get("aliases", [])

                            # Add main term
                            SparseEncoder._vocabulary[term_lower] = {
                                "idx": idx,
                                "category": category,
                                "weight": weight
                                * self.category_weights.get(category, 1.0),
                            }
                            SparseEncoder._term_to_idx[term_lower] = idx
                            idx += 1

                            # Add aliases
                            for alias in aliases:
                                alias_lower = alias.lower()
                                if alias_lower not in SparseEncoder._vocabulary:
                                    SparseEncoder._vocabulary[alias_lower] = {
                                        "idx": idx,
                                        "category": category,
                                        "weight": weight
                                        * self.category_weights.get(category, 1.0)
                                        * 0.9,
                                    }
                                    SparseEncoder._term_to_idx[alias_lower] = idx
                                    idx += 1
                else:
                    # Format: {"BRCA1": {"category": "genes", ...}, ...}
                    for term, info in raw_vocab.items():
                        term_lower = term.lower()
                        category = info.get("category", "general")
                        weight = info.get("weight", 1.0)
                        aliases = info.get("aliases", [])

                        # Add main term
                        SparseEncoder._vocabulary[term_lower] = {
                            "idx": idx,
                            "category": category,
                            "weight": weight * self.category_weights.get(category, 1.0),
                        }
                        SparseEncoder._term_to_idx[term_lower] = idx
                        idx += 1

                        # Add aliases
                        for alias in aliases:
                            alias_lower = alias.lower()
                            if alias_lower not in SparseEncoder._vocabulary:
                                SparseEncoder._vocabulary[alias_lower] = {
                                    "idx": idx,
                                    "category": category,
                                    "weight": weight
                                    * self.category_weights.get(category, 1.0)
                                    * 0.9,
                                }
                                SparseEncoder._term_to_idx[alias_lower] = idx
                                idx += 1

                logger.info(
                    f"✅ SparseEncoder loaded {len(SparseEncoder._vocabulary)} terms from bio_vocabulary.json"
                )

            except Exception as e:
                logger.warning(f"Failed to load bio_vocabulary.json: {e}")
                self._build_default_vocabulary()
        else:
            logger.warning("bio_vocabulary.json not found, using default vocabulary")
            self._build_default_vocabulary()

    def _build_default_vocabulary(self):
        """Build a minimal default vocabulary."""
        default_terms = {
            # Genes
            "brca1": {"category": "genes", "weight": 3.0},
            "brca2": {"category": "genes", "weight": 3.0},
            "tp53": {"category": "genes", "weight": 3.0},
            "egfr": {"category": "genes", "weight": 3.0},
            "kras": {"category": "genes", "weight": 3.0},
            "parp1": {"category": "genes", "weight": 3.0},
            "atm": {"category": "genes", "weight": 3.0},
            "rad51": {"category": "genes", "weight": 3.0},
            # Diseases
            "cancer": {"category": "diseases", "weight": 2.5},
            "breast cancer": {"category": "diseases", "weight": 2.5},
            "ovarian cancer": {"category": "diseases", "weight": 2.5},
            "tumor": {"category": "diseases", "weight": 2.5},
            "carcinoma": {"category": "diseases", "weight": 2.5},
            "diabetes": {"category": "diseases", "weight": 2.5},
            "alzheimer": {"category": "diseases", "weight": 2.5},
            # Pathways
            "dna repair": {"category": "pathways", "weight": 2.0},
            "homologous recombination": {"category": "pathways", "weight": 2.0},
            "apoptosis": {"category": "pathways", "weight": 2.0},
            "cell cycle": {"category": "pathways", "weight": 2.0},
            # Processes
            "mutation": {"category": "processes", "weight": 1.8},
            "expression": {"category": "processes", "weight": 1.8},
            "phosphorylation": {"category": "processes", "weight": 1.8},
            "inhibitor": {"category": "drugs", "weight": 2.0},
            "therapy": {"category": "drugs", "weight": 2.0},
        }

        SparseEncoder._vocabulary = {}
        SparseEncoder._term_to_idx = {}

        for idx, (term, info) in enumerate(default_terms.items()):
            SparseEncoder._vocabulary[term] = {
                "idx": idx,
                "category": info["category"],
                "weight": info["weight"],
            }
            SparseEncoder._term_to_idx[term] = idx

        logger.info(
            f"Built default vocabulary with {len(SparseEncoder._vocabulary)} terms"
        )

    def encode(self, texts: Union[str, List[str]]) -> List[dict]:
        """
        Encode text(s) to sparse vectors.

        Returns list of {"indices": [...], "values": [...]}
        """
        if isinstance(texts, str):
            texts = [texts]

        results = []
        for text in texts:
            sparse_vec = self._encode_single(text)
            results.append(sparse_vec)

        return results

    def _encode_single(self, text: str) -> dict:
        """Encode single text to sparse vector."""
        import re

        # Tokenize
        text_lower = text.lower()

        # Find matched terms
        matched_terms = {}

        # Multi-word matching (longer terms first)
        sorted_terms = sorted(SparseEncoder._vocabulary.keys(), key=len, reverse=True)

        remaining_text = text_lower

        for term in sorted_terms:
            if term in remaining_text:
                info = SparseEncoder._vocabulary[term]
                idx = info["idx"]
                weight = info["weight"]

                # Count occurrences
                count = remaining_text.count(term)
                if count > 0:
                    # BM25-style TF
                    tf = (
                        count
                        * (self.k1 + 1)
                        / (
                            count
                            + self.k1
                            * (
                                1
                                - self.b
                                + self.b * len(text.split()) / self.avg_doc_len
                            )
                        )
                    )
                    score = tf * weight

                    if idx not in matched_terms or matched_terms[idx] < score:
                        matched_terms[idx] = score

        # Also add simple word tokens
        words = re.findall(r"\b[a-z0-9]+\b", text_lower)
        for word in words:
            if len(word) > 2 and word in SparseEncoder._term_to_idx:
                idx = SparseEncoder._term_to_idx[word]
                if idx not in matched_terms:
                    info = SparseEncoder._vocabulary.get(word, {})
                    weight = info.get("weight", 1.0)
                    matched_terms[idx] = weight

        # Convert to sparse format
        if not matched_terms:
            return {"indices": [], "values": []}

        indices = list(matched_terms.keys())
        values = [matched_terms[i] for i in indices]

        # Normalize values
        max_val = max(values) if values else 1.0
        values = [v / max_val for v in values]

        return {
            "indices": indices,
            "values": values,
        }

    def extract_concepts(self, text: str) -> dict:
        """
        Extract biological concepts from text.
        Returns dict of {concept: weight}
        """
        sparse = self._encode_single(text)

        concepts = {}
        idx_to_term = {v["idx"]: k for k, v in SparseEncoder._vocabulary.items()}

        for idx, val in zip(sparse["indices"], sparse["values"]):
            if idx in idx_to_term:
                term = idx_to_term[idx]
                concepts[term] = val

        return concepts

    @property
    def vocab_size(self) -> int:
        if SparseEncoder._vocabulary:
            return len(SparseEncoder._vocabulary)
        return getattr(self, "_default_vocab_size", 30000)


# =============================================================================
# MULTI-MODAL ENCODER - Unified Interface
# =============================================================================


class MultiModalEncoder:
    """Unified interface for multi-modal encoding"""

    def __init__(self):
        logger.info(
            "Initializing MultiModalEncoder with biomedical-specialized models..."
        )
        self.text_encoder = TextEncoder()
        self.image_encoder = ImageEncoder()
        self.sequence_encoder = SequenceEncoder()
        self.structure_encoder = StructureEncoder()
        self.sparse_encoder = SparseEncoder()
        logger.info("MultiModalEncoder initialized")

    def encode_text(self, texts: Union[str, List[str]]) -> np.ndarray:
        return self.text_encoder.encode(texts)

    def encode_image(
        self, image_paths: Union[str, Path, List[Union[str, Path]]]
    ) -> np.ndarray:
        return self.image_encoder.encode(image_paths)

    def encode_sequence(self, sequences: Union[str, List[str]]) -> np.ndarray:
        return self.sequence_encoder.encode(sequences)

    def encode_structure(
        self, pdb_paths: Union[str, Path, List[Union[str, Path]]]
    ) -> np.ndarray:
        return self.structure_encoder.encode(pdb_paths)

    def encode_sparse(self, texts: Union[str, List[str]]) -> List[dict]:
        """Encode text to sparse vector (BM25-style with bio vocabulary)"""
        return self.sparse_encoder.encode(texts)

    def extract_concepts(self, text: str) -> dict:
        """Extract biological concepts from text"""
        return self.sparse_encoder.extract_concepts(text)

    def detect_and_encode(
        self,
        text: Optional[str] = None,
        sequence: Optional[str] = None,
        image_path: Optional[str] = None,
        structure_path: Optional[str] = None,
    ) -> Tuple[str, dict]:
        """Detect input type and encode accordingly"""
        vectors = {}

        has_text = text is not None and len(text.strip()) > 0

        has_sequence = False
        if sequence:
            clean_seq = "".join(
                c for c in sequence.upper() if c in "ACDEFGHIKLMNPQRSTVWYX"
            )
            if len(clean_seq) > 10:
                has_sequence = True
                vectors["sequence"] = self.sequence_encoder.encode(clean_seq)[
                    0
                ].tolist()

        has_image = image_path is not None and Path(image_path).exists()
        if has_image:
            vectors["image"] = self.image_encoder.encode(image_path)[0].tolist()

        has_structure = structure_path is not None and Path(structure_path).exists()
        if has_structure:
            vectors["structure"] = self.structure_encoder.encode(structure_path)[
                0
            ].tolist()
            title = self._extract_pdb_title(structure_path)
            if title and not has_text:
                vectors["text"] = self.text_encoder.encode(title)[0].tolist()

        if has_text:
            vectors["text"] = self.text_encoder.encode(text)[0].tolist()

        if has_text and has_sequence:
            input_type = "text_sequence"
        elif has_text and has_image:
            input_type = "text_image"
        elif has_text and has_structure:
            input_type = "text_structure"
        elif has_sequence:
            input_type = "sequence"
        elif has_image:
            input_type = "image"
        elif has_structure:
            input_type = "structure"
        elif has_text:
            input_type = "text"
        else:
            input_type = "unknown"

        return input_type, vectors

    def _extract_pdb_title(self, pdb_path: str) -> Optional[str]:
        try:
            with open(pdb_path, "r") as f:
                for line in f:
                    if line.startswith("TITLE"):
                        return line[10:].strip()
            return Path(pdb_path).stem
        except Exception:
            return Path(pdb_path).stem


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_encoder_instance = None


def get_encoder() -> MultiModalEncoder:
    """Get the singleton encoder instance"""
    global _encoder_instance
    if _encoder_instance is None:
        _encoder_instance = MultiModalEncoder()
    return _encoder_instance
