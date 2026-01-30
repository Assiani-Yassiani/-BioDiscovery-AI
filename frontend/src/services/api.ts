import axios from 'axios';
import type { SearchRequest, SearchResponse, EntityDetails, ClarificationOption } from '@/types';

const API_BASE_URL = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

interface UploadSearchParams {
  text?: string;
  sequence?: string;
  imageFile?: File;
  structureFile?: File;
  articleFile?: File;  // ← v3.3: NEW! PDF/TXT support
  topK: number;
  includeGraph: boolean;
  includeEvidence: boolean;
  filterByGenes: boolean;
  filterByDiseases: boolean;
  user_choice?: ClarificationOption;
  include_summary?: boolean;
  include_design_candidates?: boolean;
}

export const api = {
  /**
   * Main search endpoint (JSON body)
   */
  search: async (params: SearchRequest): Promise<SearchResponse> => {
    const response = await apiClient.post<SearchResponse>('/recommend', params);
    return response.data;
  },

  /**
   * Search with file upload (FormData)
   * v3.3: Now supports article_file (PDF/TXT)
   */
  searchWithUpload: async (params: UploadSearchParams): Promise<SearchResponse> => {
    const formData = new FormData();

    if (params.text) formData.append('text', params.text);
    if (params.sequence) formData.append('sequence', params.sequence);
    formData.append('top_k', params.topK.toString());
    formData.append('include_graph', params.includeGraph.toString());
    formData.append('include_evidence', params.includeEvidence.toString());
    formData.append('filter_by_genes', params.filterByGenes.toString());
    formData.append('filter_by_diseases', params.filterByDiseases.toString());

    // v2.1: Add user_choice if provided
    if (params.user_choice) {
      formData.append('user_choice', params.user_choice);
    }

    if (params.include_summary !== undefined) {
      formData.append('include_summary', params.include_summary.toString());
    }
    if (params.include_design_candidates !== undefined) {
      formData.append('include_design_candidates', params.include_design_candidates.toString());
    }

    // File uploads
    if (params.imageFile) {
      formData.append('image_file', params.imageFile);
    }
    if (params.structureFile) {
      formData.append('structure_file', params.structureFile);
    }

    // ═══════════════════════════════════════════════════════════════
    // v3.3: Article file upload (PDF/TXT)
    // ═══════════════════════════════════════════════════════════════
    if (params.articleFile) {
      formData.append('article_file', params.articleFile);
    }

    const response = await apiClient.post<SearchResponse>('/recommend/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * Search a specific collection
   */
  searchCollection: async (
    collection: string,
    text: string,
    topK: number = 10,
    genes?: string[]
  ): Promise<any> => {
    const params = new URLSearchParams({
      text,
      top_k: topK.toString(),
    });
    if (genes && genes.length > 0) {
      genes.forEach((g) => params.append('genes', g));
    }
    const response = await apiClient.post(`/search/${collection}?${params.toString()}`);
    return response.data;
  },

  /**
   * Get entity details
   */
  getEntityDetails: async (collection: string, entityId: string): Promise<EntityDetails> => {
    const response = await apiClient.get<EntityDetails>(`/entity/${collection}/${entityId}`);
    return response.data;
  },

  /**
   * Get neighbor graph for an entity
   */
  getNeighborGraph: async (entityId: string, collection: string, depth: number = 1) => {
    const response = await apiClient.post('/graph/neighbors', null, {
      params: { entity_id: entityId, collection, depth },
    });
    return response.data;
  },

  /**
   * Health check
   */
  healthCheck: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  /**
   * Get collection stats
   */
  getCollections: async () => {
    const response = await apiClient.get('/collections');
    return response.data;
  },

  /**
   * Get cache stats
   */
  getCacheStats: async () => {
    const response = await apiClient.get('/cache/stats');
    return response.data;
  },

  /**
   * Clear cache
   */
  clearCache: async (level?: 'embeddings' | 'results' | 'llm' | 'all') => {
    const params = level ? { level } : {};
    const response = await apiClient.post('/cache/clear', null, { params });
    return response.data;
  },
};