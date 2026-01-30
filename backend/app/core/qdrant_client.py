"""
Qdrant Client for BioDiscovery AI
Architecture v3.2 - REAL Hybrid Search with Qdrant Native RRF Fusion

╔═══════════════════════════════════════════════════════════════════════════╗
║  CRITICAL FIX: Previous version did NOT implement hybrid search!          ║
║  This version uses Qdrant's native Prefetch + RRF (Reciprocal Rank Fusion)║
╚═══════════════════════════════════════════════════════════════════════════╝

SEARCH METHODS:
1. vector_search()      - Dense vector only (semantic similarity)
2. sparse_search()      - Sparse vector only (BM25-style keyword matching)
3. hybrid_search()      - Dense + Sparse with RRF fusion ← KEY METHOD!
4. multi_modal_search() - Multiple vectors with weighted fusion
"""

import logging
from typing import Dict, List, Any, Optional
from functools import lru_cache

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Prefetch,
    FusionQuery,
    Fusion,
    SparseVector,
)

from app.config import get_settings, COLLECTION_CONFIGS

logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantManager:
    """
    Manager class for Qdrant operations with REAL hybrid search.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            )
            self.client.get_collections()
            logger.info(
                f"✅ Connected to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Remote Qdrant failed ({e}), using in-memory mode")
            self.client = QdrantClient(":memory:")
            logger.info("✅ Using in-memory Qdrant")

        self._initialized = True

    # ════════════════════════════════════════════════════════════════════════════
    # COLLECTION MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    def create_collection(
        self, name: str, config: Dict[str, Any], recreate: bool = False
    ) -> bool:
        """Create collection with dense AND sparse vectors."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == name for c in collections)

            if exists:
                if recreate:
                    self.client.delete_collection(name)
                    logger.info(f"🗑️ Deleted existing collection: {name}")
                else:
                    logger.info(f"📦 Collection {name} already exists")
                    return True

            # Dense vectors
            vectors_config = {}
            for vec_name, dim in config.get("vectors", {}).items():
                vectors_config[vec_name] = VectorParams(
                    size=dim, distance=Distance.COSINE
                )

            # Sparse vectors (for BM25-style keyword search)
            sparse_vectors_config = {}
            for sparse_name in config.get("sparse_vectors", []):
                sparse_vectors_config[sparse_name] = SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )

            self.client.create_collection(
                collection_name=name,
                vectors_config=vectors_config,
                sparse_vectors_config=(
                    sparse_vectors_config if sparse_vectors_config else None
                ),
            )

            logger.info(f"✅ Created collection: {name}")
            logger.info(f"   ├─ Dense vectors: {list(vectors_config.keys())}")
            logger.info(f"   └─ Sparse vectors: {list(sparse_vectors_config.keys())}")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating collection {name}: {e}")
            return False

    def create_all_collections(self, recreate: bool = False):
        """Create all configured collections."""
        for name, config in COLLECTION_CONFIGS.items():
            self.create_collection(name, config, recreate)

    def upsert_points(self, collection: str, points: List[Dict[str, Any]]) -> int:
        """
        Upsert points with BOTH dense and sparse vectors.

        Point format:
        {
            "vectors": {
                "text": [0.1, 0.2, ...],           # Dense
                "text_sparse": {"indices": [...], "values": [...]}  # Sparse
            },
            "payload": {...}
        }
        """
        from app.models.schemas import get_id_from_document

        try:
            qdrant_points = []

            for point in points:
                point_id = get_id_from_document(collection, point.get("payload", {}))

                # Separate dense and sparse vectors
                all_vectors = {}

                for vec_name, vec_data in point.get("vectors", {}).items():
                    if isinstance(vec_data, dict) and "indices" in vec_data:
                        # Sparse vector
                        if vec_data.get("indices") and vec_data.get("values"):
                            all_vectors[vec_name] = SparseVector(
                                indices=vec_data["indices"],
                                values=vec_data["values"],
                            )
                    elif isinstance(vec_data, list) and len(vec_data) > 0:
                        # Dense vector
                        all_vectors[vec_name] = vec_data

                qdrant_points.append(
                    PointStruct(
                        id=point_id,
                        vector=all_vectors,
                        payload=point.get("payload", {}),
                    )
                )

            self.client.upsert(collection_name=collection, points=qdrant_points)
            logger.info(f"📥 Upserted {len(qdrant_points)} points to {collection}")
            return len(qdrant_points)

        except Exception as e:
            logger.error(f"❌ Error upserting to {collection}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return 0

    # ════════════════════════════════════════════════════════════════════════════
    # 1. VECTOR SEARCH (Dense only)
    # ════════════════════════════════════════════════════════════════════════════

    def vector_search(
        self,
        collection: str,
        vector: List[float],
        vector_name: str = "text",
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Simple dense vector search.

        Use when: Text-only queries, single modality.
        """
        try:
            query_filter = self._build_filter(filter_dict) if filter_dict else None

            logger.debug(f"🔍 VECTOR_SEARCH: {collection}/{vector_name} (k={top_k})")

            results = self.client.query_points(
                collection_name=collection,
                query=vector,
                using=vector_name,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            formatted = [
                {
                    "id": str(point.id),
                    "score": point.score if hasattr(point, "score") else 0.0,
                    "payload": point.payload or {},
                }
                for point in results.points
            ]

            logger.debug(f"   └─ Found {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"❌ Vector search error ({collection}/{vector_name}): {e}")
            return []

    # ════════════════════════════════════════════════════════════════════════════
    # 2. SPARSE SEARCH (BM25-style keyword matching)
    # ════════════════════════════════════════════════════════════════════════════

    def sparse_search(
        self,
        collection: str,
        sparse_indices: List[int],
        sparse_values: List[float],
        sparse_name: str = "text_sparse",
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sparse vector search (BM25-style keyword matching).

        Use when: Exact keyword matching is important.
        """
        try:
            if not sparse_indices or not sparse_values:
                logger.warning("⚠️ Empty sparse vector")
                return []

            query_filter = self._build_filter(filter_dict) if filter_dict else None

            logger.debug(
                f"🔍 SPARSE_SEARCH: {collection}/{sparse_name} ({len(sparse_indices)} terms)"
            )

            sparse_vector = SparseVector(indices=sparse_indices, values=sparse_values)

            results = self.client.query_points(
                collection_name=collection,
                query=sparse_vector,
                using=sparse_name,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            formatted = [
                {
                    "id": str(point.id),
                    "score": point.score if hasattr(point, "score") else 0.0,
                    "payload": point.payload or {},
                }
                for point in results.points
            ]

            logger.debug(f"   └─ Found {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"❌ Sparse search error ({collection}/{sparse_name}): {e}")
            return []

    # ════════════════════════════════════════════════════════════════════════════
    # 3. HYBRID SEARCH - REAL Implementation with Qdrant Native RRF Fusion
    # ════════════════════════════════════════════════════════════════════════════

    def hybrid_search(
        self,
        collection: str,
        dense_vector: List[float],
        sparse_indices: Optional[List[int]] = None,
        sparse_values: Optional[List[float]] = None,
        dense_name: str = "text",
        sparse_name: str = "text_sparse",
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        fusion_method: str = "rrf",
    ) -> List[Dict[str, Any]]:
        """
        ╔═══════════════════════════════════════════════════════════════════════╗
        ║  REAL HYBRID SEARCH with Qdrant Native RRF Fusion                     ║
        ╠═══════════════════════════════════════════════════════════════════════╣
        ║                                                                       ║
        ║  COMBINES:                                                            ║
        ║  • Dense vector search (semantic similarity)                          ║
        ║    → "cancer" finds "tumor", "malignancy", "neoplasm"                ║
        ║                                                                       ║
        ║  • Sparse vector search (BM25-style keyword matching)                 ║
        ║    → "BRCA1" finds exact "BRCA1" mentions                            ║
        ║                                                                       ║
        ║  FUSION METHODS:                                                      ║
        ║  • RRF (Reciprocal Rank Fusion) - Default, best for most cases       ║
        ║  • DBSF (Distribution-Based Score Fusion)                             ║
        ║                                                                       ║
        ╚═══════════════════════════════════════════════════════════════════════╝
        """
        try:
            # ════════════════════════════════════════════════════════════════
            # FALLBACK: No sparse vector → use dense-only
            # ════════════════════════════════════════════════════════════════
            if (
                sparse_indices is None
                or sparse_values is None
                or len(sparse_indices) == 0
            ):
                logger.info(
                    f"🔍 HYBRID→DENSE: No sparse vector, using dense-only for {collection}"
                )
                return self.vector_search(
                    collection=collection,
                    vector=dense_vector,
                    vector_name=dense_name,
                    top_k=top_k,
                    filter_dict=filter_dict,
                )

            query_filter = self._build_filter(filter_dict) if filter_dict else None

            # ════════════════════════════════════════════════════════════════
            # LOG HYBRID SEARCH PARAMETERS
            # ════════════════════════════════════════════════════════════════
            logger.info(
                f"╔═══════════════════════════════════════════════════════════════╗"
            )
            logger.info(f"║  🔀 HYBRID SEARCH: {collection}")
            logger.info(
                f"╠═══════════════════════════════════════════════════════════════╣"
            )
            logger.info(f"║  Dense vector: {dense_name} (dim={len(dense_vector)})")
            logger.info(
                f"║  Sparse vector: {sparse_name} ({len(sparse_indices)} terms)"
            )
            logger.info(f"║  Fusion method: {fusion_method.upper()}")
            logger.info(f"║  Top-K: {top_k}")
            logger.info(
                f"╚═══════════════════════════════════════════════════════════════╝"
            )

            # ════════════════════════════════════════════════════════════════
            # QDRANT NATIVE HYBRID SEARCH WITH PREFETCH + RRF
            # ════════════════════════════════════════════════════════════════

            sparse_vector = SparseVector(indices=sparse_indices, values=sparse_values)

            results = self.client.query_points(
                collection_name=collection,
                prefetch=[
                    # Dense vector prefetch
                    Prefetch(
                        query=dense_vector,
                        using=dense_name,
                        limit=top_k * 2,
                    ),
                    # Sparse vector prefetch
                    Prefetch(
                        query=sparse_vector,
                        using=sparse_name,
                        limit=top_k * 2,
                    ),
                ],
                query=FusionQuery(
                    fusion=Fusion.RRF if fusion_method == "rrf" else Fusion.DBSF,
                ),
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            formatted = [
                {
                    "id": str(point.id),
                    "score": point.score if hasattr(point, "score") else 0.0,
                    "payload": point.payload or {},
                }
                for point in results.points
            ]

            logger.info(f"   ✅ HYBRID SEARCH: {len(formatted)} results (fused)")

            # Log top 3 results
            for i, r in enumerate(formatted[:3]):
                name = (
                    r["payload"].get("title") or r["payload"].get("protein_name") or "?"
                )
                logger.debug(f"      [{i+1}] {name[:40]}... (score: {r['score']:.4f})")

            return formatted

        except Exception as e:
            logger.error(f"❌ Hybrid search error ({collection}): {e}")
            logger.warning(f"   ⚠️ Falling back to dense-only search")
            return self.vector_search(
                collection=collection,
                vector=dense_vector,
                vector_name=dense_name,
                top_k=top_k,
                filter_dict=filter_dict,
            )

    # ════════════════════════════════════════════════════════════════════════════
    # 4. MULTI-MODAL FUSION SEARCH
    # Combines multiple dense vectors (text, image, structure) with RRF
    # ════════════════════════════════════════════════════════════════════════════

    def multi_modal_search(
        self,
        collection: str,
        vectors: Dict[str, List[float]],
        sparse_data: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        fusion_method: str = "rrf",
    ) -> List[Dict[str, Any]]:
        """
        Multi-modal fusion search combining multiple vector types.

        Args:
            vectors: Dict of {vector_name: vector} (e.g., {"text": [...], "image": [...]})
            sparse_data: Optional {"indices": [...], "values": [...]}
        """
        try:
            if not vectors:
                logger.warning("⚠️ No vectors provided")
                return []

            query_filter = self._build_filter(filter_dict) if filter_dict else None

            logger.info(f"🎯 MULTI-MODAL SEARCH: {collection}")
            logger.info(f"   ├─ Modalities: {list(vectors.keys())}")
            if sparse_data:
                logger.info(
                    f"   ├─ Sparse: {len(sparse_data.get('indices', []))} terms"
                )
            logger.info(f"   └─ Fusion: {fusion_method.upper()}")

            # Build prefetch queries
            prefetch_queries = []

            for vec_name, vector in vectors.items():
                if vector and len(vector) > 0:
                    prefetch_queries.append(
                        Prefetch(query=vector, using=vec_name, limit=top_k * 2)
                    )

            # Add sparse vector if available
            if sparse_data and sparse_data.get("indices") and sparse_data.get("values"):
                sparse_name = (
                    "caption_sparse" if collection == "images" else "text_sparse"
                )
                prefetch_queries.append(
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_data["indices"],
                            values=sparse_data["values"],
                        ),
                        using=sparse_name,
                        limit=top_k * 2,
                    )
                )

            if len(prefetch_queries) == 0:
                logger.warning("⚠️ No valid vectors for prefetch")
                return []

            if len(prefetch_queries) == 1:
                # Single modality
                pq = prefetch_queries[0]
                results = self.client.query_points(
                    collection_name=collection,
                    query=pq.query,
                    using=pq.using,
                    limit=top_k,
                    query_filter=query_filter,
                    with_payload=True,
                )
            else:
                # Multiple modalities → fusion
                results = self.client.query_points(
                    collection_name=collection,
                    prefetch=prefetch_queries,
                    query=FusionQuery(
                        fusion=Fusion.RRF if fusion_method == "rrf" else Fusion.DBSF,
                    ),
                    limit=top_k,
                    query_filter=query_filter,
                    with_payload=True,
                )

            formatted = [
                {
                    "id": str(point.id),
                    "score": point.score if hasattr(point, "score") else 0.0,
                    "payload": point.payload or {},
                }
                for point in results.points
            ]

            logger.info(
                f"   ✅ {len(formatted)} results ({len(prefetch_queries)} modalities fused)"
            )
            return formatted

        except Exception as e:
            logger.error(f"❌ Multi-modal search error ({collection}): {e}")
            # Fallback to first vector
            if vectors:
                first_name, first_vec = next(iter(vectors.items()))
                return self.vector_search(
                    collection=collection,
                    vector=first_vec,
                    vector_name=first_name,
                    top_k=top_k,
                    filter_dict=filter_dict,
                )
            return []

    # ════════════════════════════════════════════════════════════════════════════
    # LEGACY METHODS (for backward compatibility)
    # ════════════════════════════════════════════════════════════════════════════

    def multi_vector_search(
        self,
        collection: str,
        vectors: Dict[str, List[float]],
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Legacy method - redirects to multi_modal_search."""
        return self.multi_modal_search(
            collection=collection,
            vectors=vectors,
            top_k=top_k,
            filter_dict=filter_dict,
        )

    # ════════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════════════════════

    def _build_filter(self, filter_dict: Dict[str, Any]) -> Optional[Filter]:
        """Build Qdrant filter from dict."""
        if not filter_dict:
            return None

        conditions = []
        for field, value in filter_dict.items():
            if isinstance(value, list):
                conditions.append(FieldCondition(key=field, match=MatchAny(any=value)))
            else:
                conditions.append(
                    FieldCondition(key=field, match=MatchValue(value=value))
                )

        return Filter(must=conditions) if conditions else None

    def get_collection_stats(self, collection: str) -> Optional[Dict[str, Any]]:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(collection)
            return {
                "points_count": info.points_count,
                "vectors_count": getattr(info, "vectors_count", info.points_count),
                "status": str(info.status) if hasattr(info, "status") else "unknown",
            }
        except Exception as e:
            logger.error(f"Error getting stats for {collection}: {e}")
            return None

    def list_collections(self) -> List[str]:
        """List all collection names."""
        try:
            return [c.name for c in self.client.get_collections().collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def count_documents_with_field(
        self, collection: str, field: str, values: List[str]
    ) -> int:
        """Count documents matching field values."""
        try:
            filter_obj = Filter(
                must=[FieldCondition(key=field, match=MatchAny(any=values))]
            )
            result = self.client.count(
                collection_name=collection, count_filter=filter_obj
            )
            return result.count
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0

    def get_point(self, collection: str, point_id: str) -> Optional[Dict[str, Any]]:
        """Get a single point by ID."""
        try:
            points = self.client.retrieve(
                collection_name=collection, ids=[point_id], with_payload=True
            )
            if points:
                return {"id": str(points[0].id), "payload": points[0].payload or {}}
            return None
        except Exception as e:
            logger.error(f"Error retrieving point {point_id}: {e}")
            return None


@lru_cache()
def get_qdrant() -> QdrantManager:
    return QdrantManager()
