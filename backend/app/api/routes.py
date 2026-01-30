"""
FastAPI Routes for BioDiscovery AI
Architecture v3.3 - With Article/PDF Upload Support
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel
import tempfile
import os
import logging

from app.models.schemas import (
    SearchRequest,
    SearchResponse,
    FilterSettings
)
from app.graph.workflow import run_recommendation
from app.core.qdrant_client import get_qdrant
from app.core.encoders import get_encoder
from app.core.cache import get_cache
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# CLARIFICATION MODELS (Architecture v2.1)
# =============================================================================

class ClarificationResponse(BaseModel):
    """User response to clarification request"""
    session_id: str
    user_choice: str


class ClarificationStatus(BaseModel):
    """Status of clarification for a session"""
    needs_clarification: bool
    clarification_request: Optional[dict] = None
    session_id: Optional[str] = None


# =============================================================================
# MAIN SEARCH ENDPOINT
# =============================================================================

@router.post("/recommend", response_model=SearchResponse)
async def recommend(request: SearchRequest):
    """
    Main recommendation endpoint
    
    Accepts text and optional paths to files.
    For file uploads, use /recommend/upload endpoint.
    """
    try:
        response = await run_recommendation(
            text=request.text,
            sequence=request.sequence,
            image_path=request.image_path,
            structure_path=request.structure_path,
            article_path=getattr(request, 'article_path', None),  # v3.3
            top_k=request.top_k,
            include_graph=request.include_graph,
            include_evidence=request.include_evidence,
            include_summary=request.include_summary,
            include_design_candidates=request.include_design_candidates,
            keyword_mode=request.keyword_mode,
            manual_genes=request.manual_genes,
            manual_diseases=request.manual_diseases,
            filter_settings=request.filter_settings.model_dump() if request.filter_settings else None,
            user_choice=getattr(request, 'user_choice', None)
        )
        return response
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend/upload", response_model=SearchResponse)
async def recommend_with_upload(
    text: Optional[str] = Form(None),
    sequence: Optional[str] = Form(None),
    top_k: int = Form(5),
    include_graph: bool = Form(False),
    include_evidence: bool = Form(True),
    include_summary: bool = Form(True),
    include_design_candidates: bool = Form(True),
    keyword_mode: str = Form("llm"),
    manual_genes: Optional[str] = Form(None),
    manual_diseases: Optional[str] = Form(None),
    filter_by_genes: bool = Form(True),
    filter_by_diseases: bool = Form(False),
    user_choice: Optional[str] = Form(None),  # v2.1
    image_file: Optional[UploadFile] = File(None),
    structure_file: Optional[UploadFile] = File(None),
    article_file: Optional[UploadFile] = File(None)  # ← v3.3: NEW!
):
    """
    Recommendation endpoint with file upload support
    
    Supports:
    - image_file: PNG, JPG, WebP images
    - structure_file: PDB files
    - article_file: PDF or TXT files (NEW in v3.3)
    """
    image_path = None
    structure_path = None
    article_path = None
    
    try:
        # Handle image upload
        if image_file:
            suffix = os.path.splitext(image_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await image_file.read()
                tmp.write(content)
                image_path = tmp.name
                logger.info(f"📷 Image uploaded: {image_file.filename} → {image_path}")
        
        # Handle structure upload
        if structure_file:
            suffix = os.path.splitext(structure_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await structure_file.read()
                tmp.write(content)
                structure_path = tmp.name
                logger.info(f"🔮 Structure uploaded: {structure_file.filename} → {structure_path}")
        
        # ═══════════════════════════════════════════════════════════════
        # v3.3: Handle article upload (PDF/TXT)
        # ═══════════════════════════════════════════════════════════════
        if article_file:
            suffix = os.path.splitext(article_file.filename)[1].lower()
            if suffix not in ['.pdf', '.txt']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid article format: {suffix}. Only PDF and TXT are supported."
                )
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await article_file.read()
                tmp.write(content)
                article_path = tmp.name
                logger.info(f"📄 Article uploaded: {article_file.filename} → {article_path}")
        
        # Build filter settings
        filter_settings = {
            "filter_by_genes": filter_by_genes,
            "filter_by_diseases": filter_by_diseases,
            "filter_by_pathways": False
        }
        
        # Parse manual keywords
        parsed_genes = manual_genes.split(",") if manual_genes else None
        parsed_diseases = manual_diseases.split(",") if manual_diseases else None
        
        # Run recommendation
        response = await run_recommendation(
            text=text,
            sequence=sequence,
            image_path=image_path,
            structure_path=structure_path,
            article_path=article_path,  # ← v3.3: Pass article path
            top_k=top_k,
            include_graph=include_graph,
            include_evidence=include_evidence,
            include_summary=include_summary,
            include_design_candidates=include_design_candidates,
            keyword_mode=keyword_mode,
            manual_genes=parsed_genes,
            manual_diseases=parsed_diseases,
            filter_settings=filter_settings,
            user_choice=user_choice
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload recommendation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp files
        for path in [image_path, structure_path, article_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {path}: {e}")


# =============================================================================
# INDIVIDUAL COLLECTION SEARCH
# =============================================================================

@router.post("/search/{collection}")
async def search_collection(
    collection: str,
    text: str,
    top_k: int = Query(10, ge=1, le=50),
    genes: Optional[List[str]] = Query(None)
):
    """Search a specific collection"""
    valid_collections = ["proteins", "articles", "images", "experiments", "structures"]
    if collection not in valid_collections:
        raise HTTPException(status_code=400, detail=f"Invalid collection. Must be one of: {valid_collections}")
    
    try:
        encoder = get_encoder()
        qdrant = get_qdrant()
        
        # Encode text
        vector = encoder.encode_text(text)[0].tolist()
        
        # Build filters
        filters = None
        if genes:
            filters = {"normalized_bridge.genes": genes}
        
        # Determine vector name
        vector_name = "caption" if collection == "images" else "text"
        
        # Search
        results = qdrant.vector_search(
            collection=collection,
            vector=vector,
            vector_name=vector_name,
            top_k=top_k,
            filter_dict=filters
        )
        
        return {"collection": collection, "results": results}
        
    except Exception as e:
        logger.error(f"Collection search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTITY DETAILS
# =============================================================================

@router.get("/entity/{collection}/{entity_id}")
async def get_entity_details(collection: str, entity_id: str):
    """Get detailed information about a specific entity"""
    try:
        qdrant = get_qdrant()
        
        points = qdrant.client.retrieve(
            collection_name=collection,
            ids=[entity_id],
            with_payload=True
        )
        
        if not points:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        point = points[0]
        payload = point.payload
        
        # Get related items
        bridge = payload.get("normalized_bridge", {})
        genes = bridge.get("genes", [])
        
        related = {}
        if genes:
            related["articles"] = qdrant.count_documents_with_field(
                "articles", "normalized_bridge.genes", genes
            )
            related["experiments"] = qdrant.count_documents_with_field(
                "experiments", "normalized_bridge.genes", genes
            )
            related["structures"] = qdrant.count_documents_with_field(
                "structures", "normalized_bridge.genes", genes
            )
        
        return {
            "id": entity_id,
            "collection": collection,
            "payload": payload,
            "related_counts": related
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ADMIN/UTILITY ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        qdrant = get_qdrant()
        collections = qdrant.list_collections()
        return {
            "status": "healthy",
            "collections": collections,
            "version": getattr(settings, 'APP_VERSION', '3.3')
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    try:
        cache = get_cache()
        return cache.stats()
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(level: Optional[str] = Query(None)):
    """Clear cache"""
    try:
        cache = get_cache()
        
        if level == "all" or level is None:
            cache.clear_all()
            return {"message": "All caches cleared"}
        elif level == "embeddings":
            cache.embeddings.clear()
            return {"message": "Embeddings cache cleared"}
        elif level == "results":
            cache.results.clear()
            return {"message": "Results cache cleared"}
        elif level == "llm":
            cache.llm.clear()
            return {"message": "LLM cache cleared"}
        else:
            raise HTTPException(status_code=400, detail=f"Invalid cache level: {level}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def list_collections():
    """List all collections with stats"""
    try:
        qdrant = get_qdrant()
        collections = qdrant.list_collections()
        
        stats = {}
        for name in collections:
            stats[name] = qdrant.get_collection_stats(name)
        
        return {"collections": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections/create")
async def create_collections(recreate: bool = False):
    """Create all collections"""
    try:
        qdrant = get_qdrant()
        qdrant.create_all_collections(recreate=recreate)
        return {"message": "Collections created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GRAPH ENDPOINT
# =============================================================================

@router.post("/graph/neighbors")
async def get_neighbors(
    entity_id: str,
    collection: str,
    depth: int = Query(1, ge=1, le=2)
):
    """Get neighbor graph for a specific entity"""
    try:
        qdrant = get_qdrant()
        
        points = qdrant.client.retrieve(
            collection_name=collection,
            ids=[entity_id],
            with_payload=True
        )
        
        if not points:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        center = points[0]
        bridge = center.payload.get("normalized_bridge", {})
        genes = bridge.get("genes", [])
        
        nodes = [{
            "id": entity_id,
            "label": center.payload.get("protein_name") or center.payload.get("title") or entity_id,
            "type": collection.rstrip("s"),
            "collection": collection,
            "is_center": True
        }]
        edges = []
        
        if genes:
            encoder = get_encoder()
            
            for coll in ["proteins", "articles", "images", "experiments", "structures"]:
                results = qdrant.vector_search(
                    collection=coll,
                    vector=encoder.encode_text(" ".join(genes))[0].tolist(),
                    vector_name="text" if coll != "images" else "caption",
                    top_k=5,
                    filter_dict={"normalized_bridge.genes": genes}
                )
                
                for r in results:
                    if r["id"] == entity_id:
                        continue
                    
                    payload = r.get("payload", {})
                    nodes.append({
                        "id": r["id"],
                        "label": payload.get("protein_name") or payload.get("title") or payload.get("caption", "")[:50],
                        "type": coll.rstrip("s"),
                        "collection": coll,
                        "score": r.get("score", 0)
                    })
                    
                    r_bridge = payload.get("normalized_bridge", {})
                    shared = list(set(genes) & set(r_bridge.get("genes", [])))
                    
                    edges.append({
                        "source": entity_id,
                        "target": r["id"],
                        "relation": "shared_genes",
                        "strength": len(shared) / max(len(genes), 1),
                        "shared": shared[:3]
                    })
        
        return {
            "nodes": nodes[:20],
            "edges": edges[:40]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Neighbor graph error: {e}")
        raise HTTPException(status_code=500, detail=str(e))