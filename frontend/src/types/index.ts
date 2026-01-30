// ============================================================================
// API Types - BioDiscovery AI v3.3
// ============================================================================

export interface NormalizedBridge {
  genes: string[];
  diseases: string[];
  processes: string[];
  pathways: string[];
  keywords: string[];
}

export interface ResultItem {
  id: string;
  collection: CollectionType;
  name: string;
  description?: string;
  score: number;
  payload: Record<string, any>;
  diversity_score?: number;
  novelty_score?: number;
  final_score?: number;
  evidence?: EvidenceData;
}

export interface EvidenceData {
  confidence: number;
  article_count: number;
  experiment_count: number;
  structure_count: number;
  top_articles: Array<Record<string, any>>;
  links: Record<string, string>;
}

export interface DesignCandidate {
  id: string;
  name: string;
  collection: string;
  scores: Record<string, number>;
  shared_attributes: Record<string, string[]>;
  different_attributes: Record<string, string>;
  justification: string;
  research_suggestion?: string;
  // v2.1: Verification labels
  confidence?: 'established' | 'emerging' | 'exploratory';
  confidence_icon?: string;
  evidence_count?: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  collection: string;
  score?: number;
  is_center?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  strength: number;
  shared: string[];
}

export interface NeighborGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters?: Array<Record<string, any>>;
}

export interface QuadrantResults {
  proteins: ResultItem[];
  articles: ResultItem[];
  images: ResultItem[];
  experiments: ResultItem[];
  structures: ResultItem[];
}

// Architecture v2.1 - Clarification Types
export type ClarificationOption = 'intersection' | 'text_priority' | 'modal_priority' | 'multi_track';

export interface ClarificationRequest {
  message: string;
  options: ClarificationOption[];
  default_choice: ClarificationOption;
  timeout_seconds: number;
  context_modal: string[];
  context_text: string[];
}

export interface SearchResponse {
  input_type: string;
  processing_time: number;
  extracted_entities: {
    genes: string[];
    diseases: string[];
    pathways: string[];
    processes: string[];
  };
  quadrant: QuadrantResults;
  design_candidates: DesignCandidate[];
  evidence: Record<string, EvidenceData>;
  neighbor_graph?: NeighborGraph;
  summary: string;

  // Architecture v2.1 fields
  needs_clarification?: boolean;
  clarification_request?: ClarificationRequest;
  divergence_level?: 'aligned' | 'partial' | 'divergent';
  search_strategy?: string;
  concepts?: Record<string, number>;
}

export interface FilterSettings {
  filter_by_genes: boolean;
  filter_by_diseases: boolean;
  filter_by_pathways: boolean;
  min_score: number;
}

export interface SearchRequest {
  text?: string;
  sequence?: string;
  image_path?: string;
  structure_path?: string;
  article_path?: string;  // ← v3.3: NEW - Article/PDF path
  top_k: number;
  include_graph: boolean;
  include_evidence: boolean;
  include_design_candidates: boolean;
  include_summary?: boolean;
  filter_settings?: FilterSettings;
  user_choice?: ClarificationOption;  // Architecture v2.1
}

// ============================================================================
// UI Types
// ============================================================================

export type CollectionType = 'proteins' | 'articles' | 'images' | 'experiments' | 'structures';

export type InputType =
  | 'text'
  | 'sequence'
  | 'image'
  | 'structure'
  | 'article'  // ← v3.3: NEW
  | 'text_sequence'
  | 'text_image'
  | 'text_structure'
  | 'text_article';  // ← v3.3: NEW

export interface TabItem {
  id: CollectionType;
  label: string;
  icon: string;
  color: string;
  count?: number;
}

export interface EntityDetails {
  id: string;
  collection: CollectionType;
  payload: Record<string, any>;
  related_counts?: Record<string, number>;
}

// ============================================================================
// Store Types
// ============================================================================

export interface SearchState {
  // Input
  query: string;
  sequence: string;
  imageFile: File | null;
  structureFile: File | null;
  articleFile: File | null;  // ← v3.3: NEW - Article file (PDF/TXT)

  // Settings
  topK: number;
  includeGraph: boolean;
  includeEvidence: boolean;
  includeSummary: boolean;
  includeDesignAssistant: boolean;
  filterSettings: FilterSettings;
  keywordMode: 'llm' | 'manual' | 'none';
  manualKeywords: { genes: string; diseases: string };

  // Results
  results: SearchResponse | null;
  isLoading: boolean;
  error: string | null;

  // UI State
  activeTab: CollectionType;
  selectedEntity: EntityDetails | null;
  showSettingsModal: boolean;
  showEntityModal: boolean;

  // Architecture v2.1 - Clarification State
  needsClarification: boolean;
  clarificationRequest: ClarificationRequest | null;
  showClarificationModal: boolean;
  userChoice: ClarificationOption | null;

  // Actions
  setQuery: (query: string) => void;
  setSequence: (sequence: string) => void;
  setImageFile: (file: File | null) => void;
  setStructureFile: (file: File | null) => void;
  setArticleFile: (file: File | null) => void;  // ← v3.3: NEW
  setTopK: (topK: number) => void;
  setIncludeGraph: (include: boolean) => void;
  setIncludeEvidence: (include: boolean) => void;
  setIncludeSummary: (include: boolean) => void;
  setIncludeDesignAssistant: (include: boolean) => void;
  setFilterSettings: (settings: Partial<FilterSettings>) => void;
  setKeywordMode: (mode: 'llm' | 'manual' | 'none') => void;
  setManualKeywords: (keywords: { genes: string; diseases: string }) => void;
  setActiveTab: (tab: CollectionType) => void;
  setSelectedEntity: (entity: EntityDetails | null) => void;
  setShowSettingsModal: (show: boolean) => void;
  setShowEntityModal: (show: boolean) => void;
  setShowClarificationModal: (show: boolean) => void;
  setUserChoice: (choice: ClarificationOption | null) => void;
  search: () => Promise<void>;
  searchWithChoice: (choice: ClarificationOption) => Promise<void>;
  reset: () => void;
}

// ============================================================================
// Component Props
// ============================================================================

export interface ResultCardProps {
  result: ResultItem;
  onClick?: () => void;
}

export interface GraphVisualizationProps {
  graph: NeighborGraph;
  onNodeClick?: (nodeId: string) => void;
}

export interface SequenceViewerProps {
  sequence: string;
  geneNames?: string[];
}

export interface DesignCandidateCardProps {
  candidate: DesignCandidate;
  onClick?: () => void;
}

// ============================================================================
// API Upload Types - v3.3
// ============================================================================

export interface UploadSearchParams {
  text?: string;
  sequence?: string;
  imageFile?: File;
  structureFile?: File;
  articleFile?: File;  // ← v3.3: NEW - PDF/TXT article file
  topK: number;
  includeGraph: boolean;
  includeEvidence: boolean;
  filterByGenes: boolean;
  filterByDiseases: boolean;
  user_choice?: ClarificationOption;
  include_summary?: boolean;
  include_design_candidates?: boolean;
}

// ============================================================================
// Image Types - v3.3 (for protein screenshots)
// ============================================================================

export interface ImageDocument {
  source: string;  // KEGG, HPA, UniProt, PDB, AlphaFold, custom
  image_type: string;  // pathway, gene_profile, network, microscopy, protein_screenshot
  file_path: string;
  url?: string;
  caption: string;
  description?: string;

  // Gene profile specific (Human Protein Atlas)
  gene_name?: string;
  prognostic_data?: Array<{
    cancer: string;
    prognostic: 'favorable' | 'unfavorable';
    pvalue: number;
  }>;
  expression_data?: Record<string, any>;
  cancer_types?: string[];

  // Protein screenshot specific (v3.3)
  uniprot_id?: string;
  protein_name?: string;

  normalized_bridge?: NormalizedBridge;
}