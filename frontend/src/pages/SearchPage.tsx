import { motion, AnimatePresence } from 'framer-motion';
import { useSearchStore } from '@/stores/searchStore';
import SearchBar from '@/components/features/SearchBar';
import ResultsQuadrant from '@/components/features/ResultsQuadrant';
import DesignCandidates from '@/components/features/DesignCandidates';
import NeighborGraph from '@/components/features/NeighborGraph';
import EntityModal from '@/components/modals/EntityModal';
import SettingsModal from '@/components/modals/SettingsModal';
import ClarificationModal from '@/components/modals/ClarificationModal';
import { Loader2, AlertCircle, Clock, Sparkles, FileText, Dna, Image, FlaskConical, Box } from 'lucide-react';

// Input type icons and labels for user-friendly display
const INPUT_TYPE_INFO: Record<string, { icon: any; label: string; color: string }> = {
  'text': { icon: FileText, label: 'Text Query', color: 'text-blue-400' },
  'sequence': { icon: Dna, label: 'Protein Sequence', color: 'text-green-400' },
  'structure': { icon: Box, label: '3D Structure', color: 'text-purple-400' },
  'image': { icon: Image, label: 'Image', color: 'text-pink-400' },
  'text_sequence': { icon: Dna, label: 'Text + Sequence', color: 'text-cyan-400' },
  'text_structure': { icon: Box, label: 'Text + Structure', color: 'text-violet-400' },
  'text_image': { icon: Image, label: 'Text + Image', color: 'text-rose-400' },
};

export default function SearchPage() {
  const { results, isLoading, error, showEntityModal, showSettingsModal, showClarificationModal } = useSearchStore();

  return (
    <div className="max-w-7xl mx-auto">
      {/* Search Section */}
      <section className="mb-8">
        <SearchBar />
      </section>

      {/* Error Display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center gap-3"
          >
            <AlertCircle className="text-red-400" />
            <span className="text-red-300">{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading State */}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-20"
          >
            <Loader2 className="w-12 h-12 text-primary-500 animate-spin mb-4" />
            <p className="text-dark-400">Searching across all collections...</p>
            <p className="text-sm text-dark-500 mt-2">This may take a few seconds</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {!isLoading && results && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            {/* ════════════════════════════════════════════════════════════
                SUMMARY CARD - Clean design, no technical details
                ════════════════════════════════════════════════════════════ */}
            {results.summary && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="card p-6 mb-6"
              >
                {/* Header with icon */}
                <div className="flex items-start gap-3 mb-4">
                  <div className="p-2 rounded-lg bg-primary-500/20">
                    <Sparkles size={20} className="text-primary-400" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-dark-100 mb-1">Summary</h3>
                    <p className="text-dark-300 leading-relaxed">{results.summary}</p>
                  </div>
                </div>
                
                {/* Entity badges */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {results.extracted_entities.genes.slice(0, 5).map((gene) => (
                    <span key={gene} className="badge-protein">{gene}</span>
                  ))}
                  {results.extracted_entities.diseases.slice(0, 3).map((disease) => (
                    <span key={disease} className="badge-article">{disease}</span>
                  ))}
                </div>
                
                {/* Clean metadata row - NO "Strategy: CAS_2" */}
                <div className="flex items-center gap-4 text-sm border-t border-dark-700 pt-4">
                  {/* Processing time */}
                  <div className="flex items-center gap-1.5 text-dark-400">
                    <Clock size={14} />
                    <span>{results.processing_time.toFixed(1)}s</span>
                  </div>
                  
                  {/* Input type - User friendly */}
                  {results.input_type && INPUT_TYPE_INFO[results.input_type] && (
                    <div className="flex items-center gap-1.5">
                      {(() => {
                        const info = INPUT_TYPE_INFO[results.input_type];
                        const Icon = info.icon;
                        return (
                          <>
                            <Icon size={14} className={info.color} />
                            <span className={info.color}>{info.label}</span>
                          </>
                        );
                      })()}
                    </div>
                  )}
                  
                  {/* Alignment status - Only show if relevant */}
                  {results.divergence_level && (
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs ${
                      results.divergence_level === 'aligned' 
                        ? 'bg-green-500/20 text-green-400' 
                        : results.divergence_level === 'partial' 
                        ? 'bg-yellow-500/20 text-yellow-400' 
                        : 'bg-orange-500/20 text-orange-400'
                    }`}>
                      {results.divergence_level === 'aligned' && '✓ Well matched'}
                      {results.divergence_level === 'partial' && '◐ Partial match'}
                      {results.divergence_level === 'divergent' && '◎ Exploratory'}
                    </div>
                  )}
                  
                  {/* Results count */}
                  <div className="flex items-center gap-1.5 text-dark-500 ml-auto">
                    <span>
                      {Object.values(results.quadrant).reduce((acc, arr) => acc + arr.length, 0)} results
                    </span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Main Results Grid */}
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Results Quadrant (Main) */}
              <div className="lg:col-span-2">
                <ResultsQuadrant />
              </div>

              {/* Sidebar */}
              <div className="space-y-6">
                {/* Neighbor Graph */}
                {results.neighbor_graph && (
                  <NeighborGraph graph={results.neighbor_graph} />
                )}
                
                {/* Design Candidates */}
                {results.design_candidates.length > 0 && (
                  <DesignCandidates candidates={results.design_candidates} />
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!isLoading && !results && !error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-20"
        >
          <div className="w-24 h-24 rounded-full bg-dark-800 flex items-center justify-center mx-auto mb-6">
            <span className="text-4xl">🧬</span>
          </div>
          <h2 className="text-2xl font-bold text-dark-200 mb-4">
            Start Your Discovery
          </h2>
          <p className="text-dark-400 max-w-md mx-auto">
            Enter a text query, protein sequence, or upload an image/structure file to discover
            related biological entities across multiple data types.
          </p>
        </motion.div>
      )}

      {/* Modals */}
      <AnimatePresence>
        {showEntityModal && <EntityModal />}
        {showSettingsModal && <SettingsModal />}
        {showClarificationModal && <ClarificationModal />}
      </AnimatePresence>
    </div>
  );
}