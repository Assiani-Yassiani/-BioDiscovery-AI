import { create } from 'zustand';
import { api } from '@/services/api';
import type {
  SearchResponse,
  FilterSettings,
  CollectionType,
  EntityDetails,
  ClarificationOption
} from '@/types';

interface SearchState {
  // ════════════════════════════════════════════════════════════════════════════
  // INPUT STATE
  // ════════════════════════════════════════════════════════════════════════════
  query: string;
  sequence: string;
  imageFile: File | null;
  structureFile: File | null;
  articleFile: File | null;  // ← v3.3: Article input (PDF/TXT)

  // ════════════════════════════════════════════════════════════════════════════
  // SETTINGS
  // ════════════════════════════════════════════════════════════════════════════
  topK: number;
  includeGraph: boolean;
  includeEvidence: boolean;
  includeSummary: boolean;
  includeDesignAssistant: boolean;
  filterSettings: FilterSettings;

  // Keyword extraction mode
  keywordMode: 'llm' | 'manual' | 'none';
  manualKeywords: { genes: string; diseases: string };

  // ════════════════════════════════════════════════════════════════════════════
  // RESULTS
  // ════════════════════════════════════════════════════════════════════════════
  results: SearchResponse | null;
  isLoading: boolean;
  error: string | null;

  // ════════════════════════════════════════════════════════════════════════════
  // UI STATE
  // ════════════════════════════════════════════════════════════════════════════
  activeTab: CollectionType;
  selectedEntity: EntityDetails | null;
  showSettingsModal: boolean;
  showEntityModal: boolean;

  // Clarification (Architecture v2.1)
  needsClarification: boolean;
  clarificationRequest: any;
  showClarificationModal: boolean;
  userChoice: ClarificationOption | null;

  // ════════════════════════════════════════════════════════════════════════════
  // ACTIONS
  // ════════════════════════════════════════════════════════════════════════════
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

const initialState = {
  // Input
  query: '',
  sequence: '',
  imageFile: null,
  structureFile: null,
  articleFile: null,  // ← v3.3: Initialize to null

  // Settings
  topK: 5,
  includeGraph: false,
  includeEvidence: true,
  includeSummary: true,
  includeDesignAssistant: true,
  filterSettings: {
    filter_by_genes: true,
    filter_by_diseases: false,
    filter_by_pathways: false,
    min_score: 0.3,
  },
  keywordMode: 'llm' as const,
  manualKeywords: { genes: '', diseases: '' },

  // Results
  results: null,
  isLoading: false,
  error: null,

  // UI
  activeTab: 'proteins' as CollectionType,
  selectedEntity: null,
  showSettingsModal: false,
  showEntityModal: false,

  // Clarification
  needsClarification: false,
  clarificationRequest: null,
  showClarificationModal: false,
  userChoice: null,
};

export const useSearchStore = create<SearchState>((set, get) => ({
  ...initialState,

  // ════════════════════════════════════════════════════════════════════════════
  // SETTERS
  // ════════════════════════════════════════════════════════════════════════════
  setQuery: (query) => set({ query }),
  setSequence: (sequence) => set({ sequence }),
  setImageFile: (file) => set({ imageFile: file }),
  setStructureFile: (file) => set({ structureFile: file }),
  setArticleFile: (file) => set({ articleFile: file }),  // ← v3.3: NEW

  setTopK: (topK) => set({ topK }),
  setIncludeGraph: (include) => set({ includeGraph: include }),
  setIncludeEvidence: (include) => set({ includeEvidence: include }),
  setIncludeSummary: (include) => set({ includeSummary: include }),
  setIncludeDesignAssistant: (include) => set({ includeDesignAssistant: include }),
  setFilterSettings: (settings) =>
    set((state) => ({
      filterSettings: { ...state.filterSettings, ...settings },
    })),
  setKeywordMode: (mode) => set({ keywordMode: mode }),
  setManualKeywords: (keywords) => set({ manualKeywords: keywords }),

  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedEntity: (entity) => set({ selectedEntity: entity }),
  setShowSettingsModal: (show) => set({ showSettingsModal: show }),
  setShowEntityModal: (show) => set({ showEntityModal: show }),
  setShowClarificationModal: (show) => set({ showClarificationModal: show }),
  setUserChoice: (choice) => set({ userChoice: choice }),

  // ════════════════════════════════════════════════════════════════════════════
  // SEARCH ACTION
  // ════════════════════════════════════════════════════════════════════════════
  search: async () => {
    const state = get();

    // Validate: need at least one input
    const hasInput =
      state.query.trim() ||
      state.sequence.trim() ||
      state.imageFile ||
      state.structureFile ||
      state.articleFile;  // ← v3.3: Include articleFile check

    if (!hasInput) {
      set({ error: 'Please enter a query or upload a file' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      // ════════════════════════════════════════════════════════════════
      // v3.3: Article is sent as a FILE to backend for processing
      // Backend extracts title + abstract from PDF/TXT
      // ════════════════════════════════════════════════════════════════
      const response = await api.searchWithUpload({
        text: state.query.trim() || undefined,
        sequence: state.sequence.trim() || undefined,
        imageFile: state.imageFile || undefined,
        structureFile: state.structureFile || undefined,
        articleFile: state.articleFile || undefined,  // ← v3.3: Send article file
        topK: state.topK,
        includeGraph: state.includeGraph,
        includeEvidence: state.includeEvidence,
        filterByGenes: state.filterSettings.filter_by_genes,
        filterByDiseases: state.filterSettings.filter_by_diseases,
        include_summary: state.includeSummary,
        include_design_candidates: state.includeDesignAssistant,
      });

      // Check for clarification request
      if (response.needs_clarification) {
        set({
          needsClarification: true,
          clarificationRequest: response.clarification_request,
          showClarificationModal: true,
          isLoading: false,
        });
        return;
      }

      // Determine active tab based on results
      let newActiveTab: CollectionType = state.activeTab;
      const quadrant = response.quadrant;

      if (quadrant) {
        // Find collection with most results
        const counts = {
          proteins: quadrant.proteins?.length || 0,
          articles: quadrant.articles?.length || 0,
          images: quadrant.images?.length || 0,
          experiments: quadrant.experiments?.length || 0,
          structures: quadrant.structures?.length || 0,
        };

        // Prefer modality collection if uploaded
        if (state.structureFile && counts.structures > 0) {
          newActiveTab = 'structures';
        } else if (state.imageFile && counts.images > 0) {
          newActiveTab = 'images';
        } else if (state.sequence && counts.proteins > 0) {
          newActiveTab = 'proteins';
        } else if (state.articleFile && counts.articles > 0) {
          // v3.3: If article uploaded, prefer articles tab
          newActiveTab = 'articles';
        } else {
          // Find max
          const maxCollection = Object.entries(counts).reduce((a, b) =>
            b[1] > a[1] ? b : a
          );
          if (maxCollection[1] > 0) {
            newActiveTab = maxCollection[0] as CollectionType;
          }
        }
      }

      set({
        results: response,
        isLoading: false,
        activeTab: newActiveTab,
        needsClarification: false,
        clarificationRequest: null,
      });
    } catch (error: any) {
      console.error('Search error:', error);
      set({
        error: error.response?.data?.detail || error.message || 'Search failed',
        isLoading: false,
      });
    }
  },

  // ════════════════════════════════════════════════════════════════════════════
  // SEARCH WITH CLARIFICATION CHOICE
  // ════════════════════════════════════════════════════════════════════════════
  searchWithChoice: async (choice: ClarificationOption) => {
    const state = get();

    set({
      isLoading: true,
      error: null,
      showClarificationModal: false,
      userChoice: choice,
    });

    try {
      const response = await api.searchWithUpload({
        text: state.query.trim() || undefined,
        sequence: state.sequence.trim() || undefined,
        imageFile: state.imageFile || undefined,
        structureFile: state.structureFile || undefined,
        articleFile: state.articleFile || undefined,  // ← v3.3: Include article
        topK: state.topK,
        includeGraph: state.includeGraph,
        includeEvidence: state.includeEvidence,
        filterByGenes: state.filterSettings.filter_by_genes,
        filterByDiseases: state.filterSettings.filter_by_diseases,
        user_choice: choice,
        include_summary: state.includeSummary,
        include_design_candidates: state.includeDesignAssistant,
      });

      set({
        results: response,
        isLoading: false,
        needsClarification: false,
        clarificationRequest: null,
      });
    } catch (error: any) {
      console.error('Search with choice error:', error);
      set({
        error: error.response?.data?.detail || error.message || 'Search failed',
        isLoading: false,
      });
    }
  },

  // ════════════════════════════════════════════════════════════════════════════
  // RESET
  // ════════════════════════════════════════════════════════════════════════════
  reset: () => set(initialState),
}));