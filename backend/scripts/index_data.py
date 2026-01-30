#!/usr/bin/env python3
"""
Data Indexing Script for BioDiscovery AI
Architecture v3.2 - Indexes BOTH Dense AND Sparse vectors

╔═══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS SCRIPT DOES:                                                   ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  For each document:                                                        ║
║    1. Generate DENSE vectors (semantic embeddings via Gemini/BGE)         ║
║    2. Generate SPARSE vectors (BM25-style keyword indices)                ║
║    3. Upsert to Qdrant with BOTH vector types                             ║
╚═══════════════════════════════════════════════════════════════════════════╝

WHY SPARSE VECTORS ARE CRITICAL:
- Dense vectors: "cancer" ≈ "tumor" ≈ "malignancy" (semantic)
- Sparse vectors: "BRCA1" = "BRCA1" (exact keyword match)
- Hybrid search: BEST OF BOTH WORLDS!
"""
import json
import sys
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.qdrant_client import get_qdrant
from app.core.encoders import get_encoder
from app.models.schemas import get_id_from_document
from app.config import COLLECTION_CONFIGS


def load_json(filepath: str) -> list:
    """Load JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_sparse(encoder, text: str) -> dict:
    """Extract sparse vector from text with error handling."""
    try:
        sparse_result = encoder.encode_sparse(text)

        if isinstance(sparse_result, list) and len(sparse_result) > 0:
            sparse_data = (
                sparse_result[0]
                if isinstance(sparse_result[0], dict)
                else {"indices": [], "values": []}
            )
        elif isinstance(sparse_result, dict):
            sparse_data = sparse_result
        else:
            sparse_data = {"indices": [], "values": []}

        # Validate
        if not sparse_data.get("indices") or not sparse_data.get("values"):
            return {"indices": [], "values": []}

        return sparse_data

    except Exception as e:
        logger.warning(f"   ⚠️ Sparse encoding failed: {e}")
        return {"indices": [], "values": []}


def index_proteins(data_path: str):
    """
    Index proteins collection.

    Vectors:
    - text: Dense (768) from name + function + genes
    - sequence: Dense (320) from ESM-2
    - text_sparse: Sparse (BM25) from text
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("🧬 INDEXING PROTEINS")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    encoder = get_encoder()

    proteins = load_json(data_path)
    points = []
    sparse_count = 0

    for i, protein in enumerate(proteins):
        text = f"{protein['protein_name']} {protein['function']} {' '.join(protein['gene_names'])}"

        logger.info(f"   [{i+1}/{len(proteins)}] {protein['protein_name'][:50]}...")

        # ══════════════════════════════════════════════════════════════
        # DENSE VECTORS
        # ══════════════════════════════════════════════════════════════
        text_vector = encoder.encode_text(text)[0].tolist()
        sequence_vector = encoder.encode_sequence(protein["sequence"])[0].tolist()

        # ══════════════════════════════════════════════════════════════
        # SPARSE VECTOR (BM25-style)
        # ══════════════════════════════════════════════════════════════
        sparse_data = extract_sparse(encoder, text)
        if sparse_data.get("indices"):
            sparse_count += 1
            logger.debug(f"      Sparse: {len(sparse_data['indices'])} terms")

        points.append(
            {
                "vectors": {
                    "text": text_vector,
                    "sequence": sequence_vector,
                    "text_sparse": sparse_data,  # ← SPARSE VECTOR!
                },
                "payload": protein,
            }
        )

    # Upsert
    count = qdrant.upsert_points("proteins", points)
    logger.info(f"   ✅ Indexed {count} proteins")
    logger.info(f"   📊 Sparse vectors: {sparse_count}/{len(proteins)} documents")


def index_articles(data_path: str):
    """
    Index articles collection.

    Vectors:
    - text: Dense (768) from title + abstract
    - text_sparse: Sparse (BM25) from text
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("📄 INDEXING ARTICLES")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    encoder = get_encoder()

    articles = load_json(data_path)
    points = []
    sparse_count = 0

    for i, article in enumerate(articles):
        text = f"{article['title']} {article['abstract']}"

        logger.info(f"   [{i+1}/{len(articles)}] {article['title'][:50]}...")

        # Dense
        text_vector = encoder.encode_text(text)[0].tolist()

        # Sparse
        sparse_data = extract_sparse(encoder, text)
        if sparse_data.get("indices"):
            sparse_count += 1

        points.append(
            {
                "vectors": {
                    "text": text_vector,
                    "text_sparse": sparse_data,  # ← SPARSE VECTOR!
                },
                "payload": article,
            }
        )

    count = qdrant.upsert_points("articles", points)
    logger.info(f"   ✅ Indexed {count} articles")
    logger.info(f"   📊 Sparse vectors: {sparse_count}/{len(articles)} documents")


def index_images(data_path: str):
    """
    Index images collection.

    Vectors:
    - image: Dense (512) from CLIP
    - caption: Dense (768) from caption text
    - caption_sparse: Sparse (BM25) from caption
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("🖼️ INDEXING IMAGES")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    encoder = get_encoder()

    images = load_json(data_path)
    points = []
    sparse_count = 0
    image_encoded_count = 0

    for i, image in enumerate(images):
        caption_text = f"{image['caption']} {image.get('description', '')}"

        logger.info(f"   [{i+1}/{len(images)}] {image['caption'][:50]}...")

        # Dense caption
        caption_vector = encoder.encode_text(caption_text)[0].tolist()

        # Dense image (if file exists)
        image_vector = [0.0] * 512
        image_path = image.get("file_path", "")
        if image_path and os.path.exists(image_path):
            try:
                image_vector = encoder.encode_image(image_path)[0].tolist()
                image_encoded_count += 1
                logger.debug(f"      Image encoded from: {image_path}")
            except Exception as e:
                logger.warning(f"      ⚠️ Could not encode image: {e}")

        # Sparse
        sparse_data = extract_sparse(encoder, caption_text)
        if sparse_data.get("indices"):
            sparse_count += 1

        points.append(
            {
                "vectors": {
                    "image": image_vector,
                    "caption": caption_vector,
                    "caption_sparse": sparse_data,  # ← SPARSE VECTOR!
                },
                "payload": image,
            }
        )

    count = qdrant.upsert_points("images", points)
    logger.info(f"   ✅ Indexed {count} images")
    logger.info(f"   📊 Image vectors: {image_encoded_count}/{len(images)} encoded")
    logger.info(f"   📊 Sparse vectors: {sparse_count}/{len(images)} documents")


def index_experiments(data_path: str):
    """
    Index experiments collection.

    Vectors:
    - text: Dense (768) from title + summary
    - text_sparse: Sparse (BM25) from text
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 INDEXING EXPERIMENTS")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    encoder = get_encoder()

    experiments = load_json(data_path)
    points = []
    sparse_count = 0

    for i, exp in enumerate(experiments):
        text = f"{exp['title']} {exp['summary']}"

        logger.info(f"   [{i+1}/{len(experiments)}] {exp['title'][:50]}...")

        # Dense
        text_vector = encoder.encode_text(text)[0].tolist()

        # Sparse
        sparse_data = extract_sparse(encoder, text)
        if sparse_data.get("indices"):
            sparse_count += 1

        points.append(
            {
                "vectors": {
                    "text": text_vector,
                    "text_sparse": sparse_data,
                },
                "payload": exp,
            }
        )

    count = qdrant.upsert_points("experiments", points)
    logger.info(f"   ✅ Indexed {count} experiments")
    logger.info(f"   📊 Sparse vectors: {sparse_count}/{len(experiments)} documents")


def index_structures(data_path: str):
    """
    Index structures collection.

    Vectors:
    - text: Dense (768) from title + method
    - structure: Dense (768) from PDB file
    - text_sparse: Sparse (BM25) from text
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("🔮 INDEXING STRUCTURES")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    encoder = get_encoder()

    structures = load_json(data_path)
    points = []
    sparse_count = 0
    structure_encoded_count = 0

    for i, struct in enumerate(structures):
        text = f"{struct['title']} {struct.get('method', '')} {' '.join(struct.get('uniprot_ids', []))}"

        logger.info(f"   [{i+1}/{len(structures)}] {struct['title'][:50]}...")

        # Dense text
        text_vector = encoder.encode_text(text)[0].tolist()

        # Dense structure (if PDB exists)
        structure_vector = [0.0] * 768
        pdb_path = struct.get("file_path")
        if pdb_path and os.path.exists(pdb_path):
            try:
                result = encoder.encode_structure(pdb_path)
                if result is not None:
                    if hasattr(result, "__len__") and len(result.shape) > 1:
                        structure_vector = result[0].tolist()
                    else:
                        structure_vector = result.tolist()
                    structure_encoded_count += 1
                    logger.debug(f"      Structure encoded from: {pdb_path}")
            except Exception as e:
                logger.warning(f"      ⚠️ Error encoding structure: {e}")

        # Sparse
        sparse_data = extract_sparse(encoder, text)
        if sparse_data.get("indices"):
            sparse_count += 1

        points.append(
            {
                "vectors": {
                    "text": text_vector,
                    "structure": structure_vector,
                    "text_sparse": sparse_data,
                },
                "payload": struct,
            }
        )

    count = qdrant.upsert_points("structures", points)
    logger.info(f"   ✅ Indexed {count} structures")
    logger.info(
        f"   📊 Structure vectors: {structure_encoded_count}/{len(structures)} encoded"
    )
    logger.info(f"   📊 Sparse vectors: {sparse_count}/{len(structures)} documents")


def main():
    """Main indexing function."""
    print("")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "🚀 BioDiscovery AI - Data Indexing v3.2" + " " * 8 + "║")
    print(
        "║"
        + " " * 12
        + "Indexing DENSE + SPARSE vectors for Hybrid Search"
        + " " * 5
        + "║"
    )
    print("╚" + "═" * 68 + "╝")

    # Data directory
    data_dir = Path(__file__).parent.parent / "data"

    # Initialize Qdrant and create collections
    logger.info("")
    logger.info("📦 Creating collections with Dense + Sparse config...")
    qdrant = get_qdrant()
    qdrant.create_all_collections(recreate=True)

    # Index each collection
    if (data_dir / "proteins.json").exists():
        index_proteins(str(data_dir / "proteins.json"))

    if (data_dir / "articles.json").exists():
        index_articles(str(data_dir / "articles.json"))

    if (data_dir / "images.json").exists():
        index_images(str(data_dir / "images.json"))

    if (data_dir / "experiments.json").exists():
        index_experiments(str(data_dir / "experiments.json"))

    if (data_dir / "structures.json").exists():
        index_structures(str(data_dir / "structures.json"))

    # Print final stats
    print("")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 25 + "📈 COLLECTION STATISTICS" + " " * 18 + "║")
    print("╠" + "═" * 68 + "╣")

    for name, config in COLLECTION_CONFIGS.items():
        stats = qdrant.get_collection_stats(name)
        if stats:
            dense_vecs = list(config.get("vectors", {}).keys())
            sparse_vecs = config.get("sparse_vectors", [])
            points = stats.get("points_count", 0)
            print(
                f"║  {name:12} │ {points:4} docs │ Dense: {str(dense_vecs):25} │ Sparse: {str(sparse_vecs)}"
            )

    print("╚" + "═" * 68 + "╝")
    print("")
    print("✅ INDEXING COMPLETE!")
    print("   Now you can use hybrid_search() with both dense AND sparse vectors")
    print("")


if __name__ == "__main__":
    main()
