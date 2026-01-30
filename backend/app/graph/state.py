"""
LangGraph State Definition for BioDiscovery AI Workflow
Architecture v3.0 - 3 Nodes with Bridge LLM

CAS 1: Text seul → Direct parallèle (pas de Bridge)
CAS 2: Modal seul → Phase1 Modal → Bridge → Phase3 Reste
CAS 3: Text + Modal → Phase1 Modal(3vec) → Bridge → Phase3 Reste
"""

from typing import TypedDict, Dict, List, Any, Optional, Annotated
from operator import add


class GraphState(TypedDict):
    """
    State object that flows through the LangGraph workflow
    Architecture v3.0 - 3 Nodes Pipeline

    NODE 1: ENCODE (detection + encoding)
    NODE 2: SEARCH (3 CAS logic + Bridge LLM)
    NODE 3: RANK & ENRICH (MMR + Design + Summary)
    """

    # ========== INPUT ==========
    input_text: Optional[str]
    input_sequence: Optional[str]
    input_image_path: Optional[str]
    input_structure_path: Optional[str]

    # User settings
    top_k: int
    include_graph: bool
    include_evidence: bool
    include_summary: bool
    include_design_candidates: bool
    filter_by_genes: bool  # Optionnel: utiliser filtres du Bridge

    # ========== NODE 1: ENCODE ==========
    # Input type detection
    input_type: str  # "text_only", "image", "sequence", "structure", "text_image", "text_sequence", "text_structure"
    search_case: int  # 1, 2, or 3

    # Flags
    has_text: bool
    has_modal: bool  # image, sequence, or structure
    primary_modality: Optional[
        str
    ]  # "image", "sequence", "structure" OR list for multi-modal
    modalities: List[
        str
    ]  # List of all modalities present: ["sequence", "structure"], etc.

    # Vectors
    vectors: Dict[
        str, List[float]
    ]  # {"text": [...], "image": [...], "sequence": [...], "structure": [...]}
    sparse_vectors: Dict[
        str, Dict[str, Any]
    ]  # {"text_sparse": {"indices": [], "values": []}}
    concepts: Dict[str, float]  # Extracted from sparse encoder
    cache_hits: Dict[str, bool]

    # ========== NODE 2: SEARCH ==========
    # Phase 1 results (modalités - CAS 2 & 3)
    phase1_results: Dict[str, List[Dict[str, Any]]]  # {collection: results}
    phase1_metadata: List[Dict[str, Any]]  # Metadata extracted for Bridge

    # Bridge LLM output (CAS 2 & 3 only)
    bridge_output: Optional[Dict[str, Any]]
    # Structure: {
    #   "queries": {"articles": "...", "experiments": "...", ...},
    #   "filters": {"genes": [], "diseases": [], "pathways": []},
    #   "alignment": "aligned" | "partial" | "divergent",
    #   "interpretation": "Summary text..."
    # }

    # Phase 3 results (reste - CAS 2 & 3)
    phase3_results: Dict[str, List[Dict[str, Any]]]

    # All results (merged)
    all_results: Dict[str, List[Dict[str, Any]]]

    # Search metadata
    search_strategy: str  # "CAS_1", "CAS_2", "CAS_3"
    alignment: Optional[str]  # From Bridge: "aligned", "partial", "divergent"

    # ========== NODE 3: RANK & ENRICH ==========
    # MMR reranked results
    reranked_results: Dict[str, List[Dict[str, Any]]]

    # Design Assistant
    design_candidates: List[Dict[str, Any]]

    # Summary (from Bridge or LLM)
    summary: str
    interpretation: Optional[str]  # From Bridge

    # Evidence & Graph
    evidence: Dict[str, Dict[str, Any]]
    neighbor_graph: Optional[Dict[str, Any]]

    # ========== META ==========
    processing_time: float
    errors: Annotated[List[str], add]


def create_initial_state(
    text: Optional[str] = None,
    sequence: Optional[str] = None,
    image_path: Optional[str] = None,
    structure_path: Optional[str] = None,
    top_k: int = 5,
    include_graph: bool = False,
    include_evidence: bool = True,
    include_summary: bool = True,
    include_design_candidates: bool = True,
    filter_by_genes: bool = True,
) -> GraphState:
    """Create initial state from user input - Architecture v3.0"""
    return {
        # Input
        "input_text": text,
        "input_sequence": sequence,
        "input_image_path": image_path,
        "input_structure_path": structure_path,
        # Settings
        "top_k": top_k,
        "include_graph": include_graph,
        "include_evidence": include_evidence,
        "include_summary": include_summary,
        "include_design_candidates": include_design_candidates,
        "filter_by_genes": filter_by_genes,
        # Node 1: Encode
        "input_type": "unknown",
        "search_case": 1,
        "has_text": False,
        "has_modal": False,
        "primary_modality": None,
        "modalities": [],  # Will be populated by NODE 1
        "vectors": {},
        "sparse_vectors": {},
        "concepts": {},
        "cache_hits": {},
        # Node 2: Search
        "phase1_results": {},
        "phase1_metadata": [],
        "bridge_output": None,
        "phase3_results": {},
        "all_results": {},
        "search_strategy": "CAS_1",
        "alignment": None,
        # Node 3: Rank & Enrich
        "reranked_results": {},
        "design_candidates": [],
        "summary": "",
        "interpretation": None,
        "evidence": {},
        "neighbor_graph": None,
        # Meta
        "processing_time": 0.0,
        "errors": [],
    }
