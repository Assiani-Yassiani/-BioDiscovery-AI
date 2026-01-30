"""
LangGraph Workflow Nodes for BioDiscovery AI
Architecture v3.3 - NO FUSION Fix

NODE 1: ENCODE - Detection + Encoding (~50ms)
NODE 2: SEARCH - 3 CAS Logic + Bridge LLM (~150-250ms)
NODE 3: RANK_ENRICH - MMR + Optional Enrichments (~100ms)

═══════════════════════════════════════════════════════════════
CAS 1: Text seul
  → Direct search ALL collections (dense + sparse)
  → Pas de Bridge, pas d'alignment

CAS 2: Modal seul (image/sequence/structure)
  → Phase 1: Search MODALITÉ collection
  → Phase 2: Bridge LLM (génère queries + filters)
  → Phase 3: Search RESTE collections

CAS 3: Text + Modal (v3.3 NO FUSION!)
  → Phase 1: Search MODALITÉ ONLY (no text fusion!)
    - Preserves pure modal signal (0.95 stays 0.95)
    - sequence → proteins, image → images, structure → structures
  → Phase 2: Bridge LLM (alignment check + queries)
  → Phase 3: Search RESTE collections with TEXT (hybrid)
    - Uses dense + sparse for keyword matching
═══════════════════════════════════════════════════════════════

v3.3 CRITICAL FIX:
  BEFORE: CAS 3 fused modal+text → diluted scores (0.95 → 0.3)
  AFTER:  CAS 3 keeps modal pure → accurate ranking
"""

import logging
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from app.graph.state import GraphState
from app.core.encoders import get_encoder
from app.core.qdrant_client import get_qdrant
from app.core.llm_client import get_llm
from app.core.cache import get_cache

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

COLLECTIONS = ["proteins", "articles", "images", "experiments", "structures"]

# Modality → Primary collection mapping
MODAL_TO_COLLECTION = {
    "image": "images",
    "sequence": "proteins",
    "structure": "structures",
}

# Collection → (vector_name, vector_key) mapping
COLLECTION_VECTORS = {
    "proteins": [("text", "text"), ("sequence", "sequence")],
    "articles": [("text", "text")],
    "images": [("image", "image"), ("caption", "text")],
    "experiments": [("text", "text")],
    "structures": [("text", "text"), ("structure", "structure")],
}

# MMR lambda by alignment
MMR_LAMBDA = {
    "aligned": 0.7,
    "partial": 0.5,
    "divergent": 0.3,
    None: 0.7,  # CAS 1
}


class ConfidenceLabel(str, Enum):
    ESTABLISHED = "established"
    EMERGING = "emerging"
    EXPLORATORY = "exploratory"


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def extract_vector(result) -> List[float]:
    """Extract flat vector from encoder result."""
    if hasattr(result, "numpy"):
        result = result.numpy()
    if hasattr(result, "tolist"):
        result = result.tolist()

    if isinstance(result, list):
        if len(result) == 1 and isinstance(result[0], list) and len(result[0]) > 10:
            return result[0]
        if len(result) > 10 and isinstance(result[0], (int, float)):
            return result
        if len(result) > 0:
            first = result[0]
            if hasattr(first, "tolist"):
                return first.tolist()
            if isinstance(first, list) and len(first) > 10:
                return first
    return list(result) if result is not None else []


def extract_metadata_for_bridge(results: List[Dict], max_items: int = 5) -> List[Dict]:
    """Extract metadata from Phase 1 results for Bridge LLM."""
    metadata = []

    for r in results[:max_items]:
        if not isinstance(r, dict):
            continue
        payload = r.get("payload", {})
        if not isinstance(payload, dict):
            continue

        item = {
            "score": round(r.get("score", 0), 3),
            "collection": r.get("collection", "unknown"),
        }

        # Extract key fields
        if "protein_name" in payload:
            item["name"] = payload["protein_name"]
            item["genes"] = payload.get("gene_names", [])[:5]
            item["function"] = str(payload.get("function", ""))[:200]
        elif "title" in payload:
            item["name"] = payload["title"][:100]
            item["abstract"] = str(payload.get("abstract", ""))[:200]
        elif "caption" in payload:
            item["name"] = str(payload["caption"])[:100]
            item["description"] = str(payload.get("description", ""))[:200]

        # Extract normalized_bridge if exists
        bridge = payload.get("normalized_bridge", {})
        if isinstance(bridge, dict):
            item["genes"] = item.get("genes", []) or bridge.get("genes", [])[:5]
            item["diseases"] = bridge.get("diseases", [])[:3]
            item["pathways"] = bridge.get("pathways", [])[:3]

        metadata.append(item)

    return metadata


def merge_results(results1: List[Dict], results2: List[Dict]) -> List[Dict]:
    """Merge two result lists with score averaging."""
    merged = {}

    for r in results1:
        rid = str(r.get("id", ""))
        merged[rid] = {
            "id": rid,
            "score": r.get("score", 0),
            "payload": r.get("payload", {}),
            "collection": r.get("collection", ""),
            "sources": ["modal"],
        }

    for r in results2:
        rid = str(r.get("id", ""))
        if rid in merged:
            merged[rid]["score"] = (merged[rid]["score"] + r.get("score", 0)) / 2
            merged[rid]["sources"].append("text")
        else:
            merged[rid] = {
                "id": rid,
                "score": r.get("score", 0),
                "payload": r.get("payload", {}),
                "collection": r.get("collection", ""),
                "sources": ["text"],
            }

    result_list = list(merged.values())
    result_list.sort(key=lambda x: x["score"], reverse=True)
    return result_list


# ============================================================
# NODE 1: ENCODE
# ============================================================


async def node_encode(state: GraphState) -> GraphState:
    """
    NODE 1: ENCODE (~50ms)

    - Détecte le type d'input
    - Détermine le CAS (1, 2, ou 3)
    - Encode toutes les modalités présentes
    - Sparse encoding si text présent
    """
    logger.info("=" * 70)
    logger.info("🔵 NODE 1: ENCODE")
    logger.info("=" * 70)

    encoder = get_encoder()
    cache = get_cache()

    vectors = {}
    sparse_vectors = {}
    cache_hits = {}
    concepts = {}

    # ─────────────────────────────────────────────────────────
    # DETECT INPUT TYPES
    # ─────────────────────────────────────────────────────────
    has_text = bool(state.get("input_text") and state["input_text"].strip())
    has_sequence = bool(
        state.get("input_sequence") and len(state["input_sequence"]) > 10
    )
    has_image = bool(state.get("input_image_path"))
    has_structure = bool(state.get("input_structure_path"))

    has_modal = has_sequence or has_image or has_structure

    logger.info(f"   📥 INPUT DETECTION:")
    logger.info(
        f"      text={has_text}, sequence={has_sequence}, image={has_image}, structure={has_structure}"
    )

    # ─────────────────────────────────────────────────────────
    # ENCODE TEXT (if present)
    # ─────────────────────────────────────────────────────────
    if has_text:
        text = state["input_text"]
        cache_key = f"text:{hashlib.sha256(text.encode()).hexdigest()[:16]}"

        cached = cache.get_embedding(cache_key)
        if cached:
            vectors["text"] = cached.get("vector", [])
            sparse_vectors["text_sparse"] = cached.get(
                "sparse", {"indices": [], "values": []}
            )
            concepts = cached.get("concepts", {})
            cache_hits["text"] = True
            logger.info(f"   ✅ TEXT: CACHE HIT (dim={len(vectors['text'])})")
        else:
            # Dense encoding
            text_vec = extract_vector(encoder.encode_text(text))
            vectors["text"] = text_vec

            # Sparse encoding
            try:
                sparse_result = encoder.encode_sparse(text)
                if isinstance(sparse_result, list) and len(sparse_result) > 0:
                    sparse_vectors["text_sparse"] = (
                        sparse_result[0]
                        if isinstance(sparse_result[0], dict)
                        else {"indices": [], "values": []}
                    )
                elif isinstance(sparse_result, dict):
                    sparse_vectors["text_sparse"] = sparse_result
                else:
                    sparse_vectors["text_sparse"] = {"indices": [], "values": []}
            except Exception as e:
                logger.warning(f"   ⚠️ Sparse encoding failed: {e}")
                sparse_vectors["text_sparse"] = {"indices": [], "values": []}

            # Extract concepts
            try:
                concepts = encoder.extract_concepts(text)
            except Exception:
                concepts = {}

            # Cache
            cache.set_embedding(
                cache_key,
                {
                    "vector": text_vec,
                    "sparse": sparse_vectors.get("text_sparse", {}),
                    "concepts": concepts,
                },
            )
            cache_hits["text"] = False

            sparse_count = len(sparse_vectors.get("text_sparse", {}).get("indices", []))
            logger.info(
                f"   📝 TEXT: ENCODED (dense={len(text_vec)}, sparse={sparse_count} terms)"
            )

    # ─────────────────────────────────────────────────────────
    # ENCODE SEQUENCE (if present)
    # ─────────────────────────────────────────────────────────
    if has_sequence:
        seq = state["input_sequence"]
        cache_key = f"seq:{hashlib.sha256(seq[:100].encode()).hexdigest()[:16]}"

        cached = cache.get_embedding(cache_key)
        if cached:
            vectors["sequence"] = cached.get("vector", [])
            cache_hits["sequence"] = True
            logger.info(f"   ✅ SEQUENCE: CACHE HIT (dim={len(vectors['sequence'])})")
        else:
            seq_vec = extract_vector(encoder.encode_sequence(seq))
            vectors["sequence"] = seq_vec
            cache.set_embedding(cache_key, {"vector": seq_vec})
            cache_hits["sequence"] = False
            logger.info(
                f"   🧬 SEQUENCE: ENCODED ({len(seq_vec)} dims, seq_len={len(seq)})"
            )

    # ─────────────────────────────────────────────────────────
    # ENCODE IMAGE (if present)
    # ─────────────────────────────────────────────────────────
    if has_image:
        img_path = state["input_image_path"]
        cache_key = f"img:{hashlib.sha256(img_path.encode()).hexdigest()[:16]}"

        cached = cache.get_embedding(cache_key)
        if cached:
            vectors["image"] = cached.get("vector", [])
            cache_hits["image"] = True
            logger.info(f"   ✅ IMAGE: CACHE HIT (dim={len(vectors['image'])})")
        else:
            try:
                img_vec = extract_vector(encoder.encode_image(img_path))
                vectors["image"] = img_vec
                cache.set_embedding(cache_key, {"vector": img_vec})
                cache_hits["image"] = False
                logger.info(f"   🖼️ IMAGE: ENCODED ({len(img_vec)} dims)")
            except Exception as e:
                logger.error(f"   ❌ IMAGE ENCODING FAILED: {e}")
                cache_hits["image"] = False

    # ─────────────────────────────────────────────────────────
    # ENCODE STRUCTURE (if present)
    # ─────────────────────────────────────────────────────────
    if has_structure:
        struct_path = state["input_structure_path"]
        cache_key = f"struct:{hashlib.sha256(struct_path.encode()).hexdigest()[:16]}"

        cached = cache.get_embedding(cache_key)
        if cached:
            vectors["structure"] = cached.get("vector", [])
            cache_hits["structure"] = True
            logger.info(f"   ✅ STRUCTURE: CACHE HIT (dim={len(vectors['structure'])})")
        else:
            try:
                struct_vec = extract_vector(encoder.encode_structure(struct_path))
                vectors["structure"] = struct_vec
                cache.set_embedding(cache_key, {"vector": struct_vec})
                cache_hits["structure"] = False
                logger.info(f"   🔬 STRUCTURE: ENCODED ({len(struct_vec)} dims)")
            except Exception as e:
                logger.error(f"   ❌ STRUCTURE ENCODING FAILED: {e}")
                cache_hits["structure"] = False

    # ─────────────────────────────────────────────────────────
    # DETERMINE INPUT TYPE AND SEARCH CASE
    # ─────────────────────────────────────────────────────────

    # Collect ALL present modalities (not just one!)
    modalities = []
    if has_image:
        modalities.append("image")
    if has_sequence:
        modalities.append("sequence")
    if has_structure:
        modalities.append("structure")

    logger.info(f"   🔍 MODALITIES DETECTED: {modalities}")

    # Determine search case and input type
    if has_text and len(modalities) == 0:
        # CAS 1: Text seul
        input_type = "text_only"
        search_case = 1
        primary_modality = None

    elif len(modalities) > 0 and not has_text:
        # CAS 2: Modal(s) seul(s) - peut être 1, 2, ou 3 modalités
        search_case = 2
        if len(modalities) == 1:
            input_type = modalities[0]  # "image", "sequence", or "structure"
            primary_modality = modalities[0]
        else:
            # MULTIPLE MODALITIES! ex: sequence + structure
            input_type = "_".join(sorted(modalities))  # "sequence_structure"
            primary_modality = modalities  # Liste de toutes les modalités!
            logger.info(f"   🎯 MULTI-MODAL SEARCH: {modalities}")

    elif has_text and len(modalities) > 0:
        # CAS 3: Text + Modal(s)
        search_case = 3
        if len(modalities) == 1:
            input_type = f"text_{modalities[0]}"
            primary_modality = modalities[0]
        else:
            # Text + multiple modalities
            input_type = "text_" + "_".join(sorted(modalities))
            primary_modality = modalities
            logger.info(f"   🎯 TEXT + MULTI-MODAL: {modalities}")
    else:
        input_type = "unknown"
        search_case = 1
        primary_modality = None

    # Store modalities list for later use in NODE 2
    state["modalities"] = modalities

    logger.info(f"   ─────────────────────────────────────────────")
    logger.info(f"   🎯 INPUT TYPE: {input_type}")
    logger.info(f"   🎯 SEARCH CASE: CAS {search_case}")
    logger.info(f"   🎯 MODALITIES: {modalities}")
    logger.info(f"   🎯 PRIMARY/ALL MODALITY: {primary_modality}")
    logger.info(f"   💾 CACHE: {sum(cache_hits.values())}/{len(cache_hits)} hits")
    logger.info("=" * 70)

    # Update state
    state["input_type"] = input_type
    state["search_case"] = search_case
    state["has_text"] = has_text
    state["has_modal"] = has_modal
    state["primary_modality"] = primary_modality
    state["modalities"] = modalities  # List of all modalities
    state["vectors"] = vectors
    state["sparse_vectors"] = sparse_vectors
    state["concepts"] = concepts
    state["cache_hits"] = cache_hits

    return state


# ============================================================
# NODE 2: SEARCH (3 CAS LOGIC)
# ============================================================


async def node_search(state: GraphState) -> GraphState:
    """
    NODE 2: SEARCH (~150-250ms)

    CAS 1: Text seul → Direct parallèle
    CAS 2: Modal seul → Phase1 → Bridge → Phase3
    CAS 3: Text + Modal → Phase1 fusion → Bridge → Phase3
    """
    logger.info("=" * 70)
    logger.info("🟢 NODE 2: SEARCH")
    logger.info("=" * 70)

    qdrant = get_qdrant()
    llm = get_llm()
    encoder = get_encoder()

    search_case = state["search_case"]
    top_k = state.get("top_k", 5)

    all_results = {}
    phase1_results = {}
    phase3_results = {}
    phase1_metadata = []
    bridge_output = None
    alignment = None

    logger.info(f"   📍 EXECUTING CAS {search_case} | top_k={top_k}")

    # ═══════════════════════════════════════════════════════════════
    # CAS 1: TEXT SEUL - Direct Parallel Search
    # ═══════════════════════════════════════════════════════════════
    if search_case == 1:
        logger.info("   ─────────────────────────────────────────────")
        logger.info("   📍 CAS 1: Direct parallel search (NO BRIDGE)")
        logger.info("   ─────────────────────────────────────────────")

        text_vec = state["vectors"].get("text", [])
        if not text_vec:
            logger.error("   ❌ No text vector for CAS 1!")
            state["all_results"] = {}
            state["search_strategy"] = "CAS_1_ERROR"
            return state

        # Search ALL collections in parallel
        for collection in COLLECTIONS:
            try:
                vec_name = "caption" if collection == "images" else "text"

                results = qdrant.vector_search(
                    collection=collection,
                    vector=text_vec,
                    vector_name=vec_name,
                    top_k=top_k * 2,
                )

                for r in results:
                    r["collection"] = collection

                all_results[collection] = results
                logger.info(f"   ✅ {collection}: {len(results)} results")

            except Exception as e:
                logger.error(f"   ❌ {collection}: ERROR - {e}")
                all_results[collection] = []

        state["search_strategy"] = "CAS_1"
        state["alignment"] = None

    # ═══════════════════════════════════════════════════════════════
    # CAS 2: MODAL(S) SEUL(S) - Phase1 parallèle → Bridge → Phase3
    # ═══════════════════════════════════════════════════════════════
    elif search_case == 2:
        logger.info("   ─────────────────────────────────────────────")
        logger.info("   📍 CAS 2: Modal(s) only → Bridge → REST")
        logger.info("   ─────────────────────────────────────────────")

        # Get modalities from state, or rebuild from vectors as fallback
        modalities = state.get("modalities", [])
        if not modalities:
            # Fallback: rebuild from vectors
            vectors = state.get("vectors", {})
            if "image" in vectors:
                modalities.append("image")
            if "sequence" in vectors:
                modalities.append("sequence")
            if "structure" in vectors:
                modalities.append("structure")
            logger.warning(f"   ⚠️ Rebuilt modalities from vectors: {modalities}")

        logger.info(f"   🎯 MODALITIES TO SEARCH: {modalities}")

        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: Search EACH modality collection IN PARALLEL
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🔍 PHASE 1: Searching modality collections (PARALLEL)")

        # Search IMAGE if present
        if "image" in modalities and "image" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🖼️ SEARCHING: IMAGES (image vector)")
            results = qdrant.vector_search(
                collection="images",
                vector=state["vectors"]["image"],
                vector_name="image",
                top_k=top_k * 2,
            )
            for r in results:
                r["collection"] = "images"
            phase1_results["images"] = results
            logger.info(f"      ✅ images: {len(results)} results")
            if results:
                logger.info(
                    f"         Top: {results[0].get('payload', {}).get('caption', '?')[:50]}..."
                )

        # Search SEQUENCE if present
        if "sequence" in modalities and "sequence" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🧬 SEARCHING: PROTEINS (sequence vector)")
            results = qdrant.vector_search(
                collection="proteins",
                vector=state["vectors"]["sequence"],
                vector_name="sequence",
                top_k=top_k * 2,
            )
            for r in results:
                r["collection"] = "proteins"
            phase1_results["proteins"] = results
            logger.info(f"      ✅ proteins: {len(results)} results")
            if results:
                logger.info(
                    f"         Top: {results[0].get('payload', {}).get('protein_name', '?')[:50]}..."
                )

        # Search STRUCTURE if present
        if "structure" in modalities and "structure" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🔬 SEARCHING: STRUCTURES (structure vector)")
            results = qdrant.vector_search(
                collection="structures",
                vector=state["vectors"]["structure"],
                vector_name="structure",
                top_k=top_k * 2,
            )
            for r in results:
                r["collection"] = "structures"
            phase1_results["structures"] = results
            logger.info(f"      ✅ structures: {len(results)} results")
            if results:
                logger.info(
                    f"         Top: {results[0].get('payload', {}).get('title', '?')[:50]}..."
                )

        # Summary of Phase 1
        logger.info(f"      ─────────────────────────────────────────────")
        logger.info(f"      📊 PHASE 1 SUMMARY:")
        for coll, res in phase1_results.items():
            logger.info(f"         {coll}: {len(res)} results")

        # Extract metadata for Bridge (combine ALL Phase 1 results)
        all_phase1 = []
        for items in phase1_results.values():
            all_phase1.extend(items)
        phase1_metadata = extract_metadata_for_bridge(all_phase1)
        logger.info(
            f"      📊 Extracted {len(phase1_metadata)} metadata items for Bridge"
        )

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: Bridge LLM
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🌉 PHASE 2: Bridge LLM")
        bridge_output = await llm.bridge_cross_modal(
            user_text=None,  # CAS 2: no text
            modality_metadata=phase1_metadata,
        )
        alignment = bridge_output.get("alignment", "aligned")
        logger.info(f"      ✅ Bridge: alignment={alignment}")
        logger.info(
            f"      📝 Queries generated for: {list(bridge_output.get('queries', {}).keys())}"
        )
        logger.info(
            f"      🧬 Filters: genes={bridge_output.get('filters', {}).get('genes', [])[:3]}"
        )

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: Search REST collections (not searched in Phase 1)
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🔍 PHASE 3: Searching REST collections")
        searched = set(phase1_results.keys())
        rest_collections = [c for c in COLLECTIONS if c not in searched]

        logger.info(f"      📋 Already searched in Phase 1: {list(searched)}")
        logger.info(f"      📋 REST collections to search: {rest_collections}")

        bridge_queries = bridge_output.get("queries", {})
        bridge_filters = bridge_output.get("filters", {})

        # LOG ALL BRIDGE QUERIES
        logger.info(
            f"   ╔═══════════════════════════════════════════════════════════════╗"
        )
        logger.info(
            f"   ║  📝 ALL BRIDGE QUERIES:                                       ║"
        )
        logger.info(
            f"   ╠═══════════════════════════════════════════════════════════════╣"
        )
        for coll, q in bridge_queries.items():
            q_display = q[:70] + "..." if len(str(q)) > 70 else q
            logger.info(f"   ║  {coll:12}: {q_display}")
        logger.info(
            f"   ╚═══════════════════════════════════════════════════════════════╝"
        )

        for collection in rest_collections:
            try:
                query_text = bridge_queries.get(collection, "protein function biology")

                logger.info(f"      ─────────────────────────────────────────────")
                logger.info(f"      🔎 SEARCHING: {collection.upper()}")
                logger.info(f'         Query text: "{query_text[:80]}"')

                query_vec = extract_vector(encoder.encode_text(query_text))
                logger.info(f"         Query vector: dim={len(query_vec)}")

                # Apply gene filter if enabled - BUT NOT for text-only collections!
                # articles usually don't have normalized_bridge field
                FILTERABLE_COLLECTIONS = [
                    "proteins",
                    "experiments",
                    "structures",
                    "images",
                ]

                filter_dict = None
                if state.get("filter_by_genes", False) and bridge_filters.get("genes"):
                    if collection in FILTERABLE_COLLECTIONS:
                        filter_dict = {
                            "normalized_bridge.genes": bridge_filters["genes"]
                        }
                        logger.info(f"         Filter applied: {filter_dict}")
                    else:
                        logger.info(
                            f"         Filter: SKIPPED ('{collection}' is text-only, no normalized_bridge)"
                        )
                else:
                    logger.info(f"         Filter: None")

                vec_name = "caption" if collection == "images" else "text"
                logger.info(f"         Vector name: '{vec_name}'")

                # Check collection stats
                try:
                    info = qdrant.client.get_collection(collection)
                    logger.info(
                        f"         Collection stats: {info.points_count} points"
                    )
                except Exception as ce:
                    logger.warning(f"         ⚠️ Could not get collection info: {ce}")

                results = qdrant.vector_search(
                    collection=collection,
                    vector=query_vec,
                    vector_name=vec_name,
                    top_k=top_k * 2,
                    filter_dict=filter_dict,
                )

                # RETRY without filter if 0 results and filter was applied
                if len(results) == 0 and filter_dict is not None:
                    logger.warning(
                        f"         ⚠️ 0 results with filter, RETRYING without filter..."
                    )
                    results = qdrant.vector_search(
                        collection=collection,
                        vector=query_vec,
                        vector_name=vec_name,
                        top_k=top_k * 2,
                        filter_dict=None,  # No filter
                    )
                    if results:
                        logger.info(
                            f"         ✅ Retry successful: {len(results)} results without filter"
                        )

                for r in results:
                    r["collection"] = collection

                phase3_results[collection] = results

                if len(results) == 0:
                    logger.warning(f"      ⚠️ {collection}: 0 RESULTS!")
                else:
                    logger.info(f"      ✅ {collection}: {len(results)} results")
                    for i, r in enumerate(results[:2]):
                        name = (
                            r.get("payload", {}).get("title")
                            or r.get("payload", {}).get("protein_name")
                            or "?"
                        )
                        logger.info(
                            f"         [{i+1}] {name[:50]}... (score: {r.get('score', 0):.4f})"
                        )

            except Exception as e:
                logger.error(f"      ❌ {collection}: ERROR - {e}")
                phase3_results[collection] = []

        # Merge Phase 1 + Phase 3
        all_results = {**phase1_results, **phase3_results}
        state["search_strategy"] = "CAS_2"
        state["alignment"] = alignment

    # ═══════════════════════════════════════════════════════════════
    # CAS 3: TEXT + MODAL(S) - v3.3 NO FUSION
    # Modal searches their native collections ONLY (pure signal)
    # Text searches REST collections with hybrid (dense + sparse)
    # ═══════════════════════════════════════════════════════════════
    elif search_case == 3:
        logger.info("   ─────────────────────────────────────────────")
        logger.info("   📍 CAS 3: Text + Modal(s) → NO FUSION (v3.3)")
        logger.info("   ─────────────────────────────────────────────")
        logger.info(
            "   ⚠️ v3.3 FIX: Removed text-modal fusion to prevent signal dilution"
        )
        logger.info("   ─────────────────────────────────────────────")

        # Get modalities from state, or rebuild from vectors as fallback
        modalities = state.get("modalities", [])
        if not modalities:
            # Fallback: rebuild from vectors (exclude "text")
            vectors = state.get("vectors", {})
            if "image" in vectors:
                modalities.append("image")
            if "sequence" in vectors:
                modalities.append("sequence")
            if "structure" in vectors:
                modalities.append("structure")
            logger.warning(f"   ⚠️ Rebuilt modalities from vectors: {modalities}")

        logger.info(f"   🎯 MODALITIES: {modalities} (searched SEPARATELY, no fusion)")

        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: MODAL-ONLY search (NO text fusion!)
        # Each modality searches its native collection with MODAL vector only
        # This preserves high similarity scores (0.95 stays 0.95, not diluted to 0.3)
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🔍 PHASE 1: MODAL-ONLY search (no text fusion)")

        # SEQUENCE → proteins (sequence vector only)
        if "sequence" in modalities and "sequence" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🧬 MODAL: PROTEINS (sequence vector ONLY)")

            seq_results = qdrant.vector_search(
                collection="proteins",
                vector=state["vectors"]["sequence"],
                vector_name="sequence",
                top_k=top_k * 2,  # Get more for MMR
            )

            for r in seq_results:
                r["collection"] = "proteins"
            phase1_results["proteins"] = seq_results

            # Log top scores to verify no dilution
            if seq_results:
                top_scores = [f"{r.get('score', 0):.4f}" for r in seq_results[:3]]
                logger.info(
                    f"      ✅ proteins: {len(seq_results)} results (PURE sequence)"
                )
                logger.info(
                    f"         📊 Top scores: {', '.join(top_scores)} (no dilution!)"
                )
            else:
                logger.warning(f"      ⚠️ proteins: 0 results")

        # IMAGE → images (image vector only)
        if "image" in modalities and "image" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🖼️ MODAL: IMAGES (image vector ONLY)")

            img_results = qdrant.vector_search(
                collection="images",
                vector=state["vectors"]["image"],
                vector_name="image",
                top_k=top_k * 2,
            )

            for r in img_results:
                r["collection"] = "images"
            phase1_results["images"] = img_results

            if img_results:
                top_scores = [f"{r.get('score', 0):.4f}" for r in img_results[:3]]
                logger.info(f"      ✅ images: {len(img_results)} results (PURE image)")
                logger.info(f"         📊 Top scores: {', '.join(top_scores)}")
            else:
                logger.warning(f"      ⚠️ images: 0 results")

        # STRUCTURE → structures (structure vector only)
        if "structure" in modalities and "structure" in state["vectors"]:
            logger.info(f"      ─────────────────────────────────────────────")
            logger.info(f"      🔬 MODAL: STRUCTURES (structure vector ONLY)")

            struct_results = qdrant.vector_search(
                collection="structures",
                vector=state["vectors"]["structure"],
                vector_name="structure",
                top_k=top_k * 2,
            )

            for r in struct_results:
                r["collection"] = "structures"
            phase1_results["structures"] = struct_results

            if struct_results:
                top_scores = [f"{r.get('score', 0):.4f}" for r in struct_results[:3]]
                logger.info(
                    f"      ✅ structures: {len(struct_results)} results (PURE structure)"
                )
                logger.info(f"         📊 Top scores: {', '.join(top_scores)}")
            else:
                logger.warning(f"      ⚠️ structures: 0 results")

        # Summary of Phase 1
        logger.info(f"      ─────────────────────────────────────────────")
        logger.info(f"      📊 PHASE 1 MODAL SUMMARY (no fusion):")
        for coll, res in phase1_results.items():
            logger.info(f"         {coll}: {len(res)} results (pure modal signal)")

        # Extract metadata for Bridge
        all_phase1 = []
        for items in phase1_results.values():
            all_phase1.extend(items)
        phase1_metadata = extract_metadata_for_bridge(all_phase1)
        logger.info(
            f"      📊 Extracted {len(phase1_metadata)} metadata items for Bridge"
        )

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: Bridge LLM (use modal results to understand context)
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🌉 PHASE 2: Bridge LLM (with alignment check)")
        bridge_output = await llm.bridge_cross_modal(
            user_text=state["input_text"],  # CAS 3: with text
            modality_metadata=phase1_metadata,
        )
        alignment = bridge_output.get("alignment", "aligned")
        logger.info(f"      ✅ Bridge: alignment={alignment}")
        if alignment != "aligned":
            logger.warning(f"      ⚠️ DIVERGENCE DETECTED: {alignment}")

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: TEXT search on REST collections (hybrid: dense + sparse)
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"   🔍 PHASE 3: TEXT search on REST collections (hybrid)")
        searched = set(phase1_results.keys())
        rest_collections = [c for c in COLLECTIONS if c not in searched]

        logger.info(f"      📋 Modal searched in Phase 1: {list(searched)}")
        logger.info(f"      📋 Text search on REST: {rest_collections}")

        bridge_queries = bridge_output.get("queries", {})
        bridge_filters = bridge_output.get("filters", {})

        # LOG ALL BRIDGE QUERIES
        logger.info(
            f"   ╔═══════════════════════════════════════════════════════════════╗"
        )
        logger.info(
            f"   ║  📝 BRIDGE QUERIES FOR TEXT SEARCH (CAS 3 v3.3):              ║"
        )
        logger.info(
            f"   ╠═══════════════════════════════════════════════════════════════╣"
        )
        for coll, q in bridge_queries.items():
            q_display = q[:70] + "..." if len(str(q)) > 70 else q
            logger.info(f"   ║  {coll:12}: {q_display}")
        logger.info(
            f"   ╚═══════════════════════════════════════════════════════════════╝"
        )

        # Get text vectors for hybrid search
        text_vec = state["vectors"].get("text", [])
        sparse_vec = state.get("sparse_vectors", {}).get("text")

        for collection in rest_collections:
            try:
                # Use Bridge query OR fallback to user text
                query_text = (
                    bridge_queries.get(collection)
                    or state.get("input_text")
                    or "biological function"
                )

                logger.info(f"      ─────────────────────────────────────────────")
                logger.info(f"      🔎 TEXT SEARCH: {collection.upper()}")
                logger.info(f'         Query: "{query_text[:60]}..."')

                # Re-encode if using bridge query (different from user text)
                if query_text != state.get("input_text"):
                    query_vec = extract_vector(encoder.encode_text(query_text))
                    query_sparse = (
                        encoder.encode_sparse(query_text)
                        if hasattr(encoder, "encode_sparse")
                        else None
                    )
                else:
                    query_vec = text_vec
                    query_sparse = sparse_vec

                # Apply gene filter if enabled
                FILTERABLE_COLLECTIONS = [
                    "proteins",
                    "experiments",
                    "structures",
                    "images",
                ]
                filter_dict = None
                if state.get("filter_by_genes", False) and bridge_filters.get("genes"):
                    if collection in FILTERABLE_COLLECTIONS:
                        filter_dict = {
                            "normalized_bridge.genes": bridge_filters["genes"]
                        }
                        logger.info(f"         Filter: {filter_dict}")
                    else:
                        logger.info(
                            f"         Filter: SKIPPED ('{collection}' is text-only)"
                        )

                vec_name = "caption" if collection == "images" else "text"
                sparse_name = (
                    f"{vec_name}_sparse" if vec_name != "caption" else "caption_sparse"
                )

                # Try hybrid search first (dense + sparse)
                try:
                    # Extract sparse indices and values from dict
                    sparse_indices = None
                    sparse_values = None
                    if query_sparse and isinstance(query_sparse, dict):
                        sparse_indices = query_sparse.get("indices", [])
                        sparse_values = query_sparse.get("values", [])

                    if (
                        sparse_indices
                        and sparse_values
                        and hasattr(qdrant, "hybrid_search")
                    ):
                        results = qdrant.hybrid_search(
                            collection=collection,
                            dense_vector=query_vec,
                            sparse_indices=sparse_indices,
                            sparse_values=sparse_values,
                            dense_name=vec_name,
                            sparse_name=sparse_name,
                            top_k=top_k * 2,
                            filter_dict=filter_dict,
                        )
                        logger.info(
                            f"         Mode: HYBRID (dense + {len(sparse_indices)} sparse terms)"
                        )
                    else:
                        # Fallback to dense-only
                        results = qdrant.vector_search(
                            collection=collection,
                            vector=query_vec,
                            vector_name=vec_name,
                            top_k=top_k * 2,
                            filter_dict=filter_dict,
                        )
                        logger.info(f"         Mode: DENSE only")
                except Exception as hybrid_err:
                    logger.warning(
                        f"         ⚠️ Hybrid failed, using dense: {hybrid_err}"
                    )
                    results = qdrant.vector_search(
                        collection=collection,
                        vector=query_vec,
                        vector_name=vec_name,
                        top_k=top_k * 2,
                        filter_dict=filter_dict,
                    )

                # RETRY without filter if 0 results
                if len(results) == 0 and filter_dict is not None:
                    logger.warning(
                        f"         ⚠️ 0 results with filter, retrying without..."
                    )
                    results = qdrant.vector_search(
                        collection=collection,
                        vector=query_vec,
                        vector_name=vec_name,
                        top_k=top_k * 2,
                        filter_dict=None,
                    )

                for r in results:
                    r["collection"] = collection

                phase3_results[collection] = results

                if len(results) == 0:
                    logger.warning(f"      ⚠️ {collection}: 0 RESULTS")
                else:
                    logger.info(f"      ✅ {collection}: {len(results)} results")
                    for i, r in enumerate(results[:2]):
                        name = (
                            r.get("payload", {}).get("title")
                            or r.get("payload", {}).get("protein_name")
                            or "?"
                        )
                        logger.info(
                            f"         [{i+1}] {name[:50]}... (score: {r.get('score', 0):.4f})"
                        )

            except Exception as e:
                logger.error(f"      ❌ {collection}: ERROR - {e}")
                phase3_results[collection] = []

        # Merge Phase 1 (modal) + Phase 3 (text) - no fusion, just combine
        all_results = {**phase1_results, **phase3_results}
        state["search_strategy"] = "CAS_3"
        state["alignment"] = alignment

    # ─────────────────────────────────────────────────────────
    # Update state
    # ─────────────────────────────────────────────────────────
    total = sum(len(r) for r in all_results.values())
    logger.info(f"   ─────────────────────────────────────────────")
    logger.info(f"   📊 TOTAL: {total} results across {len(all_results)} collections")
    logger.info("=" * 70)

    state["phase1_results"] = phase1_results
    state["phase1_metadata"] = phase1_metadata
    state["phase3_results"] = phase3_results
    state["all_results"] = all_results
    state["bridge_output"] = bridge_output

    return state


# ============================================================
# NODE 3: RANK & ENRICH
# ============================================================


async def node_rank_enrich(state: GraphState) -> GraphState:
    """
    NODE 3: RANK & ENRICH (~100ms)

    - MMR scoring (TOUJOURS)
    - Design Assistant (optionnel)
    - Summary (optionnel, utilise Bridge interpretation si dispo)
    - Evidence links (optionnel)
    - Neighbor graph (optionnel)
    """
    logger.info("=" * 70)
    logger.info("🟡 NODE 3: RANK & ENRICH")
    logger.info("=" * 70)

    encoder = get_encoder()
    qdrant = get_qdrant()
    llm = get_llm()
    cache = get_cache()

    # ─────────────────────────────────────────────────────────
    # MMR SCORING (TOUJOURS)
    # ─────────────────────────────────────────────────────────
    logger.info("   📊 MMR SCORING (always enabled)")

    reranked_results = {}
    alignment = state.get("alignment")
    mmr_lambda = MMR_LAMBDA.get(alignment, 0.7)

    logger.info(f"      λ (lambda) = {mmr_lambda} (alignment={alignment})")

    for collection, results in state.get("all_results", {}).items():
        if not results:
            reranked_results[collection] = []
            continue

        valid = [r for r in results if isinstance(r, dict)]
        if not valid:
            reranked_results[collection] = []
            continue

        selected = _apply_mmr(valid[:10], mmr_lambda, state.get("top_k", 5), encoder)

        for i, r in enumerate(selected):
            r["mmr_rank"] = i + 1

        reranked_results[collection] = selected
        logger.info(f"      ✅ {collection}: {len(valid)} → {len(selected)} (MMR)")

    state["reranked_results"] = reranked_results

    # ─────────────────────────────────────────────────────────
    # DESIGN ASSISTANT (optionnel)
    # ─────────────────────────────────────────────────────────
    design_candidates = []

    if state.get("include_design_candidates", True):  # Default to True
        # Get search case
        search_case = state.get("search_case", 1)
        is_multimodal = search_case in [2, 3]
        has_text = bool((state.get("input_text") or "").strip())
        has_rich = _has_rich_results(reranked_results)
        is_exploratory = _is_exploratory_query(state.get("input_text") or "")

        logger.info(f"   🎨 DESIGN ASSISTANT CHECK:")
        logger.info(f"      ├─ search_case={search_case}")
        logger.info(f"      ├─ is_multimodal={is_multimodal} (CAS 2 or 3)")
        logger.info(f"      ├─ has_text={has_text}")
        logger.info(f"      ├─ is_exploratory={is_exploratory}")
        logger.info(f"      └─ has_rich_results={has_rich}")

        # Conditions:
        # 1. ALWAYS activate for CAS 2/3 (multimodal) - user uploaded files!
        # 2. For CAS 1 (text only), activate if exploratory OR has rich results
        should_activate = is_multimodal or is_exploratory or has_rich

        logger.info(f"      🎯 should_activate = {should_activate}")
        if should_activate:
            if is_multimodal:
                logger.info(f"         (reason: multimodal CAS {search_case})")
            elif is_exploratory:
                logger.info(f"         (reason: exploratory query)")
            else:
                logger.info(f"         (reason: rich results)")

        if should_activate:
            logger.info("   🎨 DESIGN ASSISTANT: Generating candidates...")
            try:
                # Build context for multimodal
                query_context = state.get("input_text") or ""
                if not query_context and is_multimodal:
                    # Use Bridge interpretation as context
                    bridge = state.get("bridge_output", {})
                    query_context = bridge.get(
                        "interpretation",
                        "Find related biological entities based on uploaded data",
                    )
                    logger.info(
                        f"      Using Bridge interpretation as context: {query_context[:50]}..."
                    )

                raw = await llm.generate_design_candidates(
                    query=query_context,
                    results=_flatten_results(reranked_results)[:10],
                    top_k=3,
                )
                candidates_list = (
                    raw.get("candidates", []) if isinstance(raw, dict) else []
                )

                logger.info(f"      📦 LLM returned {len(candidates_list)} candidates")

                for i, cand in enumerate(candidates_list):
                    if isinstance(cand, dict):
                        labeled = await _verify_and_label(cand, qdrant, encoder)
                        design_candidates.append(labeled)
                        name = cand.get("name", "?")
                        confidence = labeled.get("confidence", "?")
                        logger.info(
                            f"         [{i+1}] {name} → confidence: {confidence}"
                        )

                logger.info(
                    f"      ✅ Generated {len(design_candidates)} verified candidates"
                )

            except Exception as e:
                logger.error(f"      ❌ Design Assistant error: {e}")
                import traceback

                logger.error(f"      {traceback.format_exc()}")
        else:
            logger.info("   ⏭️ DESIGN ASSISTANT: SKIPPED")
            logger.info(
                "      Reason: CAS 1 (text-only) without exploratory query or rich results"
            )
            logger.info(
                "      💡 Tip: Use words like 'discover', 'explore', 'novel' OR upload files"
            )
    else:
        logger.info("   ⏭️ DESIGN ASSISTANT: DISABLED (include_design_candidates=False)")

    state["design_candidates"] = design_candidates

    # ─────────────────────────────────────────────────────────
    # SUMMARY (optionnel)
    # ─────────────────────────────────────────────────────────
    summary = ""
    interpretation = None

    if state.get("include_summary", True):
        bridge = state.get("bridge_output")
        if bridge and bridge.get("interpretation"):
            # Use Bridge interpretation (CAS 2 & 3)
            summary = bridge["interpretation"]
            interpretation = bridge["interpretation"]
            logger.info(f"   📝 SUMMARY: From Bridge ({len(summary)} chars)")
        else:
            # Generate summary (CAS 1)
            logger.info("   📝 SUMMARY: Generating with LLM...")
            try:
                summary = await llm.generate_summary(
                    query=state.get("input_text") or "",
                    results=reranked_results,
                )
                logger.info(f"      ✅ Generated ({len(summary)} chars)")
            except Exception as e:
                logger.error(f"      ❌ Summary error: {e}")
                total = sum(len(r) for r in reranked_results.values())
                summary = (
                    f"Found {total} results across {len(reranked_results)} collections."
                )
    else:
        logger.info("   ⏭️ SUMMARY: DISABLED")

    state["summary"] = summary
    state["interpretation"] = interpretation

    # ─────────────────────────────────────────────────────────
    # EVIDENCE (optionnel)
    # ─────────────────────────────────────────────────────────
    evidence = {}

    if state.get("include_evidence", True):
        logger.info("   🔗 EVIDENCE: Collecting links...")
        evidence = _collect_evidence(reranked_results)
        logger.info(f"      ✅ {len(evidence)} evidence items")
    else:
        logger.info("   ⏭️ EVIDENCE: DISABLED")

    state["evidence"] = evidence

    # ─────────────────────────────────────────────────────────
    # GRAPH (optionnel)
    # ─────────────────────────────────────────────────────────
    neighbor_graph = None

    if state.get("include_graph", False):
        logger.info("   🕸️ GRAPH: Building...")

        # Get thresholds from state (with defaults)
        score_threshold = state.get("graph_score_threshold", 0.5)
        edge_threshold = state.get("graph_edge_threshold", 0.2)

        neighbor_graph = _build_graph(
            reranked_results,
            score_threshold=score_threshold,
            edge_threshold=edge_threshold,
        )

        nodes_count = len(neighbor_graph.get("nodes", []))
        edges_count = len(neighbor_graph.get("edges", []))
        stats = neighbor_graph.get("stats", {})
        logger.info(f"      ✅ {nodes_count} nodes, {edges_count} edges")
        logger.info(
            f"      📊 Stats: {stats.get('filtered_by_score', 0)} nodes filtered, {stats.get('edges_filtered', 0)} edges filtered"
        )
    else:
        logger.info("   ⏭️ GRAPH: DISABLED")

    state["neighbor_graph"] = neighbor_graph

    logger.info("=" * 70)

    return state


# ============================================================
# HELPER FUNCTIONS FOR NODE 3
# ============================================================


def _apply_mmr(
    results: List[Dict], mmr_lambda: float, target_k: int, encoder
) -> List[Dict]:
    """Apply MMR selection with diversity/novelty scores."""
    if not results:
        return []

    # Build vectors
    vectors = {}
    for r in results:
        rid = str(r.get("id", ""))
        payload = r.get("payload", {})
        text = (
            payload.get("protein_name")
            or payload.get("title")
            or payload.get("caption", "")
        )
        if text and isinstance(text, str):
            vec = extract_vector(encoder.encode_text(text[:100]))
            if vec and len(vec) > 10:
                vectors[rid] = np.array(vec)

    # First result
    first = results[0].copy()
    first["diversity_score"] = 1.0
    first["novelty_score"] = round(first.get("score", 0.5), 4)
    first["final_score"] = round(first.get("score", 0.5), 4)

    selected = [first]
    candidates = [r.copy() for r in results[1:]]

    while len(selected) < min(target_k, len(results)) and candidates:
        best_mmr = -float("inf")
        best_idx = -1
        best_div = 0

        for idx, cand in enumerate(candidates):
            cid = str(cand.get("id", ""))
            rel = cand.get("score", 0)

            max_sim = 0
            if cid in vectors:
                for sel in selected:
                    sid = str(sel.get("id", ""))
                    if sid in vectors:
                        sim = float(
                            np.dot(vectors[cid], vectors[sid])
                            / (
                                np.linalg.norm(vectors[cid])
                                * np.linalg.norm(vectors[sid])
                                + 1e-8
                            )
                        )
                        max_sim = max(max_sim, sim)

            div = 1.0 - max_sim
            mmr = mmr_lambda * rel - (1 - mmr_lambda) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = idx
                best_div = div

        if best_idx >= 0:
            chosen = candidates.pop(best_idx)
            chosen["diversity_score"] = round(best_div, 4)
            chosen["novelty_score"] = round(chosen.get("score", 0.5) * best_div, 4)
            chosen["final_score"] = round(best_mmr, 4)
            selected.append(chosen)
        else:
            break

    return selected


def _is_exploratory_query(query: str) -> bool:
    """Check if query is exploratory."""
    if not query:
        return False
    keywords = [
        "discover",
        "explore",
        "novel",
        "new",
        "potential",
        "target",
        "candidate",
        "suggest",
        "find",
        "identify",
        "what",
        "which",
    ]
    return any(kw in query.lower() for kw in keywords)


def _has_rich_results(results: Dict[str, List]) -> bool:
    """Check if results are rich enough."""
    total = sum(len(r) for r in results.values() if isinstance(r, list))
    collections_with_results = sum(1 for r in results.values() if len(r) >= 2)
    return total >= 5 and collections_with_results >= 2


def _flatten_results(results: Dict[str, List]) -> List[Dict]:
    """Flatten results to list."""
    flat = []
    for coll, items in results.items():
        for r in items:
            if isinstance(r, dict):
                rc = r.copy()
                rc["collection"] = coll
                flat.append(rc)
    return flat


async def _verify_and_label(candidate: Dict, qdrant, encoder) -> Dict:
    """Verify candidate and assign confidence label."""
    name = candidate.get("name", "")
    if not name:
        candidate["confidence"] = ConfidenceLabel.EXPLORATORY.value
        candidate["confidence_icon"] = "💡"
        candidate["evidence_count"] = 0
        return candidate

    try:
        vec = extract_vector(encoder.encode_text(name))
        if not vec or len(vec) < 10:
            raise ValueError("Invalid vector")

        results = qdrant.vector_search("articles", vec, "text", 10)

        matching = sum(
            1
            for r in results
            if name.lower() in str(r.get("payload", {}).get("title", "")).lower()
        )

        if matching > 3:
            candidate["confidence"] = ConfidenceLabel.ESTABLISHED.value
            candidate["confidence_icon"] = "✅"
            candidate["evidence_count"] = matching * 3
        elif matching > 0:
            candidate["confidence"] = ConfidenceLabel.EMERGING.value
            candidate["confidence_icon"] = "⚠️"
            candidate["evidence_count"] = matching
        else:
            candidate["confidence"] = ConfidenceLabel.EXPLORATORY.value
            candidate["confidence_icon"] = "💡"
            candidate["evidence_count"] = 0
    except:
        candidate["confidence"] = ConfidenceLabel.EXPLORATORY.value
        candidate["confidence_icon"] = "💡"
        candidate["evidence_count"] = 0

    return candidate


def _collect_evidence(results: Dict[str, List]) -> Dict[str, Dict]:
    """Collect evidence links."""
    evidence = {}

    for collection, items in results.items():
        for r in items:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id", ""))
            payload = r.get("payload", {})

            links = {}
            if collection == "proteins":
                if payload.get("uniprot_id"):
                    links["uniprot"] = (
                        f"https://www.uniprot.org/uniprotkb/{payload['uniprot_id']}"
                    )
            elif collection == "articles":
                if payload.get("pmid"):
                    links["pubmed"] = (
                        f"https://pubmed.ncbi.nlm.nih.gov/{payload['pmid']}"
                    )
                if payload.get("doi"):
                    links["doi"] = f"https://doi.org/{payload['doi']}"
            elif collection == "structures":
                if payload.get("pdb_id"):
                    links["pdb"] = f"https://www.rcsb.org/structure/{payload['pdb_id']}"
            elif collection == "experiments":
                geo = payload.get("geo_id") or payload.get("accession")
                if geo:
                    links["geo"] = (
                        f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={geo}"
                    )

            evidence[rid] = {
                "confidence": min(1.0, r.get("score", 0) * 1.2),
                "links": links,
                "collection": collection,
            }

    return evidence


def _build_graph(
    results: Dict[str, List],
    score_threshold: float = 0.5,  # Minimum score pour inclure un node
    edge_threshold: float = 0.2,  # Minimum strength pour inclure un edge
    max_nodes_per_collection: int = 5,  # Max nodes par collection
) -> Dict[str, Any]:
    """
    Build neighbor graph with thresholds.

    Args:
        results: Reranked results by collection
        score_threshold: Minimum score to include a node (0.0 to 1.0)
        edge_threshold: Minimum edge strength to include (0.0 to 1.0)
        max_nodes_per_collection: Maximum nodes per collection

    Returns:
        {"nodes": [...], "edges": [...], "stats": {...}}
    """
    nodes = []
    edges = []
    node_ids = set()
    node_payloads = {}  # Store payloads for edge calculation

    # Stats for debugging
    stats = {
        "total_candidates": 0,
        "filtered_by_score": 0,
        "nodes_included": 0,
        "edges_included": 0,
        "edges_filtered": 0,
    }

    logger.info(
        f"      📊 Building graph (score_threshold={score_threshold}, edge_threshold={edge_threshold})"
    )

    # ─────────────────────────────────────────────────────────
    # BUILD NODES (with score threshold)
    # ─────────────────────────────────────────────────────────
    for collection, items in results.items():
        count = 0
        for r in items:
            if count >= max_nodes_per_collection:
                break
            if not isinstance(r, dict):
                continue

            stats["total_candidates"] += 1

            rid = str(r.get("id", ""))
            score = r.get("score", 0)

            # THRESHOLD CHECK
            if score < score_threshold:
                stats["filtered_by_score"] += 1
                continue

            if rid in node_ids:
                continue

            node_ids.add(rid)
            count += 1

            payload = r.get("payload", {})
            node_payloads[rid] = payload

            # Determine label
            label = (
                payload.get("protein_name")
                or payload.get("title")
                or payload.get("caption")
                or payload.get("pdb_id")
                or "Unknown"
            )
            if isinstance(label, str):
                label = label[:40]

            # Determine node color/type
            node_type = collection.rstrip("s")  # proteins -> protein

            nodes.append(
                {
                    "id": rid,
                    "label": label,
                    "type": node_type,
                    "collection": collection,
                    "score": round(score, 4),
                    "size": max(10, int(score * 30)),  # Visual size based on score
                }
            )

    stats["nodes_included"] = len(nodes)
    logger.info(
        f"         Nodes: {stats['nodes_included']} included ({stats['filtered_by_score']} filtered by score < {score_threshold})"
    )

    # LOG ALL NODES
    logger.info(
        f"         ┌─────────────────────────────────────────────────────────────┐"
    )
    logger.info(
        f"         │  📍 GRAPH NODES:                                            │"
    )
    logger.info(
        f"         ├─────────────────────────────────────────────────────────────┤"
    )
    for n in nodes:
        logger.info(
            f"         │  [{n['type']:10}] {n['label'][:35]:35} (score: {n['score']:.2f})"
        )
    logger.info(
        f"         └─────────────────────────────────────────────────────────────┘"
    )

    # ─────────────────────────────────────────────────────────
    # BUILD EDGES (with strength threshold)
    # ─────────────────────────────────────────────────────────
    node_list = list(node_ids)

    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            pi = node_payloads.get(node_list[i], {})
            pj = node_payloads.get(node_list[j], {})

            # Get normalized_bridge data
            bridge_i = pi.get("normalized_bridge", {})
            bridge_j = pj.get("normalized_bridge", {})

            # Calculate relationships
            relations = []
            total_strength = 0

            # 1. Shared genes
            genes_i = set(bridge_i.get("genes", []))
            genes_j = set(bridge_j.get("genes", []))
            shared_genes = genes_i & genes_j
            if shared_genes:
                gene_strength = min(1.0, len(shared_genes) * 0.25)
                total_strength += gene_strength
                relations.append(
                    {
                        "type": "shared_genes",
                        "strength": gene_strength,
                        "items": list(shared_genes)[:5],
                    }
                )

            # 2. Shared diseases
            diseases_i = set(bridge_i.get("diseases", []))
            diseases_j = set(bridge_j.get("diseases", []))
            shared_diseases = diseases_i & diseases_j
            if shared_diseases:
                disease_strength = min(1.0, len(shared_diseases) * 0.3)
                total_strength += disease_strength
                relations.append(
                    {
                        "type": "shared_diseases",
                        "strength": disease_strength,
                        "items": list(shared_diseases)[:3],
                    }
                )

            # 3. Shared pathways
            pathways_i = set(bridge_i.get("pathways", []))
            pathways_j = set(bridge_j.get("pathways", []))
            shared_pathways = pathways_i & pathways_j
            if shared_pathways:
                pathway_strength = min(1.0, len(shared_pathways) * 0.35)
                total_strength += pathway_strength
                relations.append(
                    {
                        "type": "shared_pathways",
                        "strength": pathway_strength,
                        "items": list(shared_pathways)[:3],
                    }
                )

            # 4. Same collection bonus
            node_i_coll = None
            node_j_coll = None
            for n in nodes:
                if n["id"] == node_list[i]:
                    node_i_coll = n["collection"]
                if n["id"] == node_list[j]:
                    node_j_coll = n["collection"]

            # Normalize total strength
            final_strength = min(1.0, total_strength)

            # THRESHOLD CHECK
            if final_strength < edge_threshold:
                stats["edges_filtered"] += 1
                continue

            if relations:  # Only add edge if there's a relationship
                # Determine primary relation type
                primary_relation = max(relations, key=lambda x: x["strength"])["type"]

                edges.append(
                    {
                        "source": node_list[i],
                        "target": node_list[j],
                        "relation": primary_relation,
                        "strength": round(final_strength, 4),
                        "width": max(1, int(final_strength * 5)),  # Visual width
                        "details": relations,
                    }
                )
                stats["edges_included"] += 1

    logger.info(
        f"         Edges: {stats['edges_included']} included ({stats['edges_filtered']} filtered by strength < {edge_threshold})"
    )

    # LOG ALL EDGES (relationships)
    if edges:
        logger.info(
            f"         ┌─────────────────────────────────────────────────────────────┐"
        )
        logger.info(
            f"         │  🔗 GRAPH EDGES (RELATIONSHIPS):                            │"
        )
        logger.info(
            f"         ├─────────────────────────────────────────────────────────────┤"
        )

        # Get node labels for display
        node_labels = {n["id"]: n["label"][:20] for n in nodes}

        for e in edges[:15]:  # Limit to 15 edges for readability
            src_label = node_labels.get(e["source"], "?")[:15]
            tgt_label = node_labels.get(e["target"], "?")[:15]
            relation = e["relation"].replace("shared_", "")
            strength = e["strength"]

            # Get shared items
            details = e.get("details", [])
            shared_items = []
            for d in details:
                shared_items.extend(d.get("items", [])[:2])
            items_str = ", ".join(shared_items[:3]) if shared_items else "?"

            logger.info(
                f"         │  {src_label:15} ←─[{relation:8} {strength:.2f}]─→ {tgt_label:15}"
            )
            logger.info(f"         │     └─ shared: {items_str}")

        if len(edges) > 15:
            logger.info(f"         │  ... and {len(edges) - 15} more edges")

        logger.info(
            f"         └─────────────────────────────────────────────────────────────┘"
        )
    else:
        logger.info(
            f"         ⚠️ No edges found - documents may not share genes/diseases/pathways"
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
        "thresholds": {
            "score": score_threshold,
            "edge": edge_threshold,
        },
    }
