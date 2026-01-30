"""
Pydantic Schemas for BioDiscovery AI
Architecture v3.3 - With Article Support
"""

import uuid
import hashlib  # ← CRITICAL: This was missing!
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# UUID Generation for Qdrant
# ============================================================================


def generate_deterministic_uuid(prefix: str, identifier: str) -> str:
    """Generate a deterministic UUID from prefix and identifier"""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    name = f"{prefix}:{identifier}"
    return str(uuid.uuid5(namespace, name))


def get_id_from_document(collection: str, doc: Dict[str, Any]) -> str:
    """
    Get or generate UUID for a document based on collection type.
    Uses MD5 hash to create consistent IDs for the same documents.
    """
    id_mappings = {
        "proteins": ("prot", "uniprot_id"),
        "articles": ("art", "pmid"),
        "images": ("img", "file_path"),
        "experiments": ("exp", "accession"),
        "structures": ("struct", "pdb_id"),
    }

    if collection in id_mappings:
        prefix, field = id_mappings[collection]
        identifier = doc.get(field) or doc.get("alphafold_id") or doc.get("title", "")

        if not identifier:
            # Fallback: create hash from all payload
            full_key = f"{prefix}:{str(doc)}"
            hash_bytes = hashlib.md5(full_key.encode()).digest()
            return str(uuid.UUID(bytes=hash_bytes[:16]))

        return generate_deterministic_uuid(prefix, str(identifier))

    # Default: random UUID
    return str(uuid.uuid4())


# ============================================================================
# Normalized Bridge (Cross-Modal Linking)
# ============================================================================


class NormalizedBridge(BaseModel):
    """Common structure for cross-modal entity linking"""

    genes: List[str] = Field(default_factory=list)
    diseases: List[str] = Field(default_factory=list)
    processes: List[str] = Field(default_factory=list)
    pathways: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


# ============================================================================
# Collection Document Models
# ============================================================================


class ProteinDocument(BaseModel):
    """Protein document schema"""

    uniprot_id: str
    protein_name: str
    gene_names: List[str] = Field(default_factory=list)
    organism: str = "Homo sapiens"
    sequence: str
    sequence_length: Optional[int] = None
    function: Optional[str] = None
    subcellular_location: Optional[str] = None
    go_terms: List[str] = Field(default_factory=list)
    diseases: List[str] = Field(default_factory=list)
    normalized_bridge: Optional[NormalizedBridge] = None

    def model_post_init(self, __context):
        if self.sequence_length is None:
            self.sequence_length = len(self.sequence)


class ArticleDocument(BaseModel):
    """Article/Publication document schema"""

    pmid: str
    title: str
    abstract: str
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    mesh_terms: List[str] = Field(default_factory=list)
    normalized_bridge: Optional[NormalizedBridge] = None


class ImageDocument(BaseModel):
    """Image document schema (pathways, gene profiles, protein screenshots)"""

    source: str  # KEGG, HPA, UniProt, PDB, custom
    image_type: str  # pathway, gene_profile, network, microscopy, protein_screenshot
    file_path: str
    url: Optional[str] = None
    caption: str
    description: Optional[str] = None

    # Gene profile specific (Human Protein Atlas)
    gene_name: Optional[str] = None
    prognostic_data: Optional[List[Dict[str, Any]]] = None
    expression_data: Optional[Dict[str, Any]] = None
    cancer_types: Optional[List[str]] = None

    # Protein screenshot specific
    uniprot_id: Optional[str] = None
    protein_name: Optional[str] = None

    normalized_bridge: Optional[NormalizedBridge] = None


class ExperimentDocument(BaseModel):
    """Experiment/Dataset document schema (GEO)"""

    accession: str  # GSE ID
    title: str
    summary: str
    organism: str = "Homo sapiens"
    data_type: str  # expression, methylation, ChIP-seq
    platform: Optional[str] = None
    n_samples: Optional[int] = None
    conditions: List[str] = Field(default_factory=list)
    normalized_bridge: Optional[NormalizedBridge] = None


class StructureDocument(BaseModel):
    """Structure document schema (PDB, AlphaFold)"""

    pdb_id: Optional[str] = None
    alphafold_id: Optional[str] = None
    title: str
    method: Optional[str] = None  # X-ray, NMR, Cryo-EM, AlphaFold
    resolution: Optional[float] = None
    uniprot_ids: List[str] = Field(default_factory=list)
    chains: List[str] = Field(default_factory=list)
    ligands: List[str] = Field(default_factory=list)
    file_path: Optional[str] = None
    normalized_bridge: Optional[NormalizedBridge] = None


# ============================================================================
# API Request/Response Models
# ============================================================================


class FilterSettings(BaseModel):
    """Filter settings for search"""

    filter_by_genes: bool = True
    filter_by_diseases: bool = False
    filter_by_pathways: bool = False
    min_score: float = 0.3


class SearchRequest(BaseModel):
    """Main search request - v3.3 with article_path"""

    text: Optional[str] = None
    sequence: Optional[str] = None
    image_path: Optional[str] = None
    structure_path: Optional[str] = None
    article_path: Optional[str] = None  # ← NEW: PDF/TXT article path
    top_k: int = Field(default=5, ge=1, le=50)
    include_graph: bool = False
    include_evidence: bool = True
    include_design_candidates: bool = True
    include_summary: bool = True
    keyword_mode: str = "llm"  # "llm", "manual", "none"
    manual_genes: Optional[List[str]] = None
    manual_diseases: Optional[List[str]] = None
    filter_settings: Optional[FilterSettings] = None
    user_choice: Optional[str] = (
        None  # v2.1: "intersection", "text_priority", "modal_priority", "multi_track"
    )


class EvidenceData(BaseModel):
    """Evidence and traceability data"""

    confidence: float = Field(ge=0.0, le=1.0)
    article_count: int = 0
    experiment_count: int = 0
    structure_count: int = 0
    top_articles: List[Dict[str, Any]] = Field(default_factory=list)
    links: Dict[str, str] = Field(default_factory=dict)


class ResultItem(BaseModel):
    """Single result item"""

    id: str
    collection: str
    name: str
    description: Optional[str] = None
    score: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    diversity_score: Optional[float] = None
    novelty_score: Optional[float] = None
    final_score: Optional[float] = None
    evidence: Optional[EvidenceData] = None

    @field_validator("id", mode="before")
    @classmethod
    def ensure_string_id(cls, v):
        return str(v) if v is not None else ""


class DesignCandidate(BaseModel):
    """Design assistant candidate"""

    id: str
    name: str
    collection: str
    scores: Dict[str, float] = Field(default_factory=dict)
    shared_attributes: Dict[str, List[str]] = Field(default_factory=dict)
    different_attributes: Dict[str, str] = Field(default_factory=dict)
    justification: str = ""
    research_suggestion: Optional[str] = None
    confidence: Optional[str] = None
    confidence_icon: Optional[str] = None
    evidence_count: Optional[int] = None

    @field_validator("id", mode="before")
    @classmethod
    def ensure_string_id(cls, v):
        return str(v) if v is not None else ""


class GraphNode(BaseModel):
    """Node in neighbor graph"""

    id: str
    label: str
    type: str
    collection: str
    score: Optional[float] = None
    is_center: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def ensure_string_id(cls, v):
        return str(v) if v is not None else ""


class GraphEdge(BaseModel):
    """Edge in neighbor graph"""

    source: str
    target: str
    relation: str
    strength: float
    shared: List[str] = Field(default_factory=list)

    @field_validator("source", "target", mode="before")
    @classmethod
    def ensure_string_id(cls, v):
        return str(v) if v is not None else ""


class NeighborGraph(BaseModel):
    """Neighbor graph structure"""

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    clusters: Optional[List[Dict[str, Any]]] = None


class QuadrantResults(BaseModel):
    """Results organized by collection"""

    proteins: List[ResultItem] = Field(default_factory=list)
    articles: List[ResultItem] = Field(default_factory=list)
    images: List[ResultItem] = Field(default_factory=list)
    experiments: List[ResultItem] = Field(default_factory=list)
    structures: List[ResultItem] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    """Clarification request for divergent inputs (v2.1)"""

    message: str = (
        "Your inputs seem to be about different topics. How would you like to search?"
    )
    options: List[str] = Field(
        default_factory=lambda: [
            "intersection",
            "text_priority",
            "modal_priority",
            "multi_track",
        ]
    )
    default_choice: str = "multi_track"
    timeout_seconds: int = 10
    context_modal: List[str] = Field(default_factory=list)
    context_text: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Complete search response"""

    input_type: str
    processing_time: float = 0.0
    extracted_entities: Dict[str, List[str]] = Field(default_factory=dict)
    quadrant: QuadrantResults = Field(default_factory=QuadrantResults)
    design_candidates: List[DesignCandidate] = Field(default_factory=list)
    evidence: Dict[str, EvidenceData] = Field(default_factory=dict)
    neighbor_graph: Optional[NeighborGraph] = None
    summary: str = ""
    needs_clarification: bool = False
    clarification_request: Optional[ClarificationRequest] = None
    divergence_level: Optional[str] = None
    search_strategy: Optional[str] = None
    concepts: Optional[Dict[str, float]] = None
