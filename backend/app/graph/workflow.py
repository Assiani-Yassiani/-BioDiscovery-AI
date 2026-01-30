"""
Main LangGraph Workflow for BioDiscovery AI
Architecture v3.0 - 3 Nodes Pipeline

═══════════════════════════════════════════════════════════════
WORKFLOW PIPELINE:

    ┌─────────┐     ┌─────────┐     ┌─────────────┐
    │ ENCODE  │ ──→ │ SEARCH  │ ──→ │ RANK_ENRICH │ ──→ END
    │ (~50ms) │     │(~200ms) │     │   (~100ms)  │
    └─────────┘     └─────────┘     └─────────────┘

    CAS 1: text → parallel all
    CAS 2: modal → Phase1 → Bridge → Phase3
    CAS 3: text+modal → Phase1 fusion → Bridge → Phase3
═══════════════════════════════════════════════════════════════

Total: ~350ms (aligned) / ~400ms (divergent)
"""

import time
from typing import Optional, Dict, Any, List
import logging

from langgraph.graph import StateGraph, END

from app.graph.state import GraphState, create_initial_state
from app.graph.nodes import (
    node_encode,
    node_search,
    node_rank_enrich,
)
from app.models.schemas import (
    SearchResponse,
    QuadrantResults,
    ResultItem,
    DesignCandidate,
    EvidenceData,
    NeighborGraph,
    GraphNode,
    GraphEdge,
)

logger = logging.getLogger(__name__)


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow - Architecture v3.0 (3 Nodes)

    NODE 1: encode      - Detection + Encoding (~50ms)
    NODE 2: search      - 3 CAS Logic + Bridge (~150-250ms)
    NODE 3: rank_enrich - MMR + Design + Summary (~100ms)
    """
    workflow = StateGraph(GraphState)

    # Add 3 nodes
    workflow.add_node("encode", node_encode)
    workflow.add_node("search", node_search)
    workflow.add_node("rank_enrich", node_rank_enrich)

    # Linear flow
    workflow.set_entry_point("encode")
    workflow.add_edge("encode", "search")
    workflow.add_edge("search", "rank_enrich")
    workflow.add_edge("rank_enrich", END)

    return workflow.compile()


# Singleton
_workflow = None


def get_workflow():
    """Get compiled workflow singleton"""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow


async def run_recommendation(
    text: Optional[str] = None,
    sequence: Optional[str] = None,
    image_path: Optional[str] = None,
    structure_path: Optional[str] = None,
    article_path: Optional[str] = None,  # NEW: PDF/TXT article input
    top_k: int = 5,
    include_graph: bool = False,
    include_evidence: bool = True,
    include_summary: bool = True,
    include_design_candidates: bool = True,
    filter_by_genes: bool = True,
    # Legacy params (ignored)
    keyword_mode: str = "local",
    manual_genes: Optional[List[str]] = None,
    manual_diseases: Optional[List[str]] = None,
    filter_settings: Optional[Dict[str, Any]] = None,
    user_choice: Optional[str] = None,
) -> SearchResponse:
    """
    Run the complete recommendation workflow - Architecture v3.3

    Supports ALL input types:
    - text only (CAS 1)
    - sequence only (CAS 2)
    - image only (CAS 2)
    - structure only (CAS 2)
    - text + sequence (CAS 3) - NO FUSION
    - text + image (CAS 3) - NO FUSION
    - text + structure (CAS 3) - NO FUSION
    - article (PDF/TXT) + optional text (extracted title+abstract)
    """
    start_time = time.time()

    # Process article if provided - extract title/abstract and concatenate with text
    if article_path:
        try:
            from app.core.article_processor import process_article_input

            text = process_article_input(
                user_query=text or "", article_path=article_path
            )
            logger.info(f"📄 Article processed, enhanced query: {len(text)} chars")
        except Exception as e:
            logger.warning(f"⚠️ Article processing failed: {e}, using original text")

    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " 🚀 BIODISCOVERY AI v3.3 - WORKFLOW START ".center(68) + "║")
    logger.info("╠" + "═" * 68 + "╣")
    logger.info(
        f"║  Text: {(text[:40] + '...') if text and len(text) > 40 else text}".ljust(69)
        + "║"
    )
    logger.info(
        f"║  Sequence: {len(sequence) if sequence else 0} chars".ljust(69) + "║"
    )
    logger.info(f"║  Image: {image_path}".ljust(69) + "║")
    logger.info(f"║  Structure: {structure_path}".ljust(69) + "║")
    logger.info(f"║  Article: {article_path}".ljust(69) + "║")
    logger.info(f"║  top_k: {top_k}".ljust(69) + "║")
    logger.info("╚" + "═" * 68 + "╝")

    # Create initial state
    initial_state = create_initial_state(
        text=text,
        sequence=sequence,
        image_path=image_path,
        structure_path=structure_path,
        top_k=top_k,
        include_graph=include_graph,
        include_evidence=include_evidence,
        include_summary=include_summary,
        include_design_candidates=include_design_candidates,
        filter_by_genes=filter_by_genes,
    )

    # Run workflow
    workflow = get_workflow()

    try:
        final_state = await workflow.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"❌ WORKFLOW FAILED: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return SearchResponse(
            input_type="error",
            processing_time=time.time() - start_time,
            extracted_entities={},
            quadrant=QuadrantResults(),
            summary=f"Error: {str(e)}",
        )

    # Build response
    response = build_response(final_state, start_time)

    logger.info("╔" + "═" * 68 + "╗")
    logger.info(
        f"║  ✅ WORKFLOW COMPLETE - {response.processing_time:.3f}s".ljust(69) + "║"
    )
    logger.info(f"║  Strategy: {response.search_strategy}".ljust(69) + "║")
    logger.info(f"║  Alignment: {response.divergence_level}".ljust(69) + "║")
    logger.info("╚" + "═" * 68 + "╝")

    return response


def build_response(state: GraphState, start_time: float) -> SearchResponse:
    """Build SearchResponse from final state"""

    # Build quadrant results
    quadrant = QuadrantResults(
        proteins=format_results(
            state["reranked_results"].get("proteins", []), "proteins"
        ),
        articles=format_results(
            state["reranked_results"].get("articles", []), "articles"
        ),
        images=format_results(state["reranked_results"].get("images", []), "images"),
        experiments=format_results(
            state["reranked_results"].get("experiments", []), "experiments"
        ),
        structures=format_results(
            state["reranked_results"].get("structures", []), "structures"
        ),
    )

    # Build evidence
    evidence = {}
    for result_id, ev_data in state.get("evidence", {}).items():
        evidence[result_id] = EvidenceData(
            confidence=ev_data.get("confidence", 0.5),
            article_count=0,
            experiment_count=0,
            structure_count=0,
            links=ev_data.get("links", {}),
        )

    # Build design candidates
    design_candidates = []
    for cand in state.get("design_candidates", []):
        design_candidates.append(
            DesignCandidate(
                id=cand.get("id", ""),
                name=cand.get("name", ""),
                collection=cand.get("collection", ""),
                scores=cand.get("scores", {}),
                shared_attributes=cand.get("shared_attributes", {}),
                different_attributes=cand.get("different_attributes", {}),
                justification=cand.get("justification", ""),
                research_suggestion=cand.get("research_suggestion"),
                confidence=cand.get("confidence"),
                confidence_icon=cand.get("confidence_icon"),
                evidence_count=cand.get("evidence_count"),
            )
        )

    # Build neighbor graph
    neighbor_graph = None
    if state.get("neighbor_graph"):
        ng = state["neighbor_graph"]
        neighbor_graph = NeighborGraph(
            nodes=[GraphNode(**n) for n in ng.get("nodes", [])],
            edges=[GraphEdge(**e) for e in ng.get("edges", [])],
        )

    # Build extracted entities from concepts
    concepts = state.get("concepts", {})
    extracted_entities = {
        "genes": [k for k in concepts.keys() if k.isupper() and len(k) > 2][:10],
        "diseases": [
            k
            for k in concepts.keys()
            if "cancer" in k.lower() or "disease" in k.lower()
        ][:5],
        "pathways": [],
        "processes": [],
        "concepts": list(concepts.keys())[:10],
    }

    # Get Bridge filters if available
    bridge = state.get("bridge_output")
    if bridge and isinstance(bridge, dict):
        filters = bridge.get("filters", {})
        if filters.get("genes"):
            extracted_entities["genes"] = filters["genes"][:10]
        if filters.get("diseases"):
            extracted_entities["diseases"] = filters["diseases"][:5]
        if filters.get("pathways"):
            extracted_entities["pathways"] = filters["pathways"][:5]

    return SearchResponse(
        input_type=state["input_type"],
        processing_time=round(time.time() - start_time, 3),
        extracted_entities=extracted_entities,
        quadrant=quadrant,
        design_candidates=design_candidates,
        evidence=evidence,
        neighbor_graph=neighbor_graph,
        summary=state.get("summary", ""),
        needs_clarification=False,
        clarification_request=None,
        divergence_level=state.get("alignment") or "aligned",
        search_strategy=state.get("search_strategy", "CAS_1"),
    )


def format_results(results: list, collection: str) -> list:
    """Format results for response"""
    formatted = []

    for r in results:
        payload = r.get("payload", {})

        if collection == "proteins":
            name = payload.get("protein_name") or (
                payload.get("gene_names", ["Unknown"])[0]
                if payload.get("gene_names")
                else "Unknown"
            )
            description = str(payload.get("function", ""))[:200]
        elif collection == "articles":
            name = payload.get("title", "Untitled")
            description = str(payload.get("abstract", ""))[:200]
        elif collection == "images":
            name = str(payload.get("caption", "Image"))[:100]
            description = str(payload.get("description", ""))[:200]
        elif collection == "experiments":
            name = payload.get("title", "Experiment")
            description = str(payload.get("summary", ""))[:200]
        elif collection == "structures":
            name = payload.get("title") or payload.get("pdb_id", "Structure")
            description = f"Method: {payload.get('method', 'Unknown')}"
        else:
            name = str(r.get("id", "Unknown"))
            description = ""

        formatted.append(
            ResultItem(
                id=str(r.get("id", "")),
                collection=collection,
                name=name,
                description=description,
                score=round(r.get("score", 0), 4),
                payload=payload,
                diversity_score=r.get("diversity_score"),
                novelty_score=r.get("novelty_score"),
                final_score=r.get("final_score"),
            )
        )

    return formatted
