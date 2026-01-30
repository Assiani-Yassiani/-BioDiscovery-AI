import { motion } from 'framer-motion';
import { X, Sliders, Filter, Sparkles, Network } from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';

export default function SettingsModal() {
  const {
    filterSettings,
    setFilterSettings,
    includeGraph,
    setIncludeGraph,
    includeSummary,
    setIncludeSummary,
    includeDesignAssistant,
    setIncludeDesignAssistant,
    topK,
    setTopK,
    setShowSettingsModal,
  } = useSearchStore();

  const handleClose = () => setShowSettingsModal(false);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={handleClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="card w-full max-w-md"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-dark-700">
          <div className="flex items-center gap-2">
            <Sliders className="text-primary-400" size={18} />
            <h2 className="font-semibold text-dark-100">Settings</h2>
          </div>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-dark-800">
            <X size={18} className="text-dark-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5">

          {/* ══════════════════════════════════════════════════════════════
              FILTERS
              ══════════════════════════════════════════════════════════════ */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Filter size={14} className="text-dark-400" />
              <span className="text-sm font-medium text-dark-200">Filters</span>
            </div>

            <div className="space-y-2">
              <ToggleOption
                label="Filter by genes"
                description="Only show results matching extracted genes"
                checked={filterSettings.filter_by_genes}
                onChange={(v) => setFilterSettings({ filter_by_genes: v })}
              />
              <ToggleOption
                label="Filter by diseases"
                description="Only show results matching extracted diseases"
                checked={filterSettings.filter_by_diseases}
                onChange={(v) => setFilterSettings({ filter_by_diseases: v })}
              />
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════════════
              FEATURES
              ══════════════════════════════════════════════════════════════ */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={14} className="text-dark-400" />
              <span className="text-sm font-medium text-dark-200">Features</span>
            </div>

            <div className="space-y-2">
              <ToggleOption
                label="Summary"
                description="Generate AI summary of results"
                checked={includeSummary}
                onChange={setIncludeSummary}
              />
              <ToggleOption
                label="Design Assistant"
                description="Suggest research candidates"
                checked={includeDesignAssistant}
                onChange={setIncludeDesignAssistant}
              />
              <ToggleOption
                label="Neighbor Graph"
                description="Visualize entity relationships"
                checked={includeGraph}
                onChange={setIncludeGraph}
              />
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════════════
              RESULTS
              ══════════════════════════════════════════════════════════════ */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Network size={14} className="text-dark-400" />
              <span className="text-sm font-medium text-dark-200">Results</span>
            </div>

            {/* Top K */}
            <div className="mb-3">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-dark-300">Per collection</span>
                <span className="text-dark-400">{topK}</span>
              </div>
              <input
                type="range"
                min={3}
                max={20}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full h-1.5 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
              />
            </div>

            {/* Min Score */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-dark-300">Min score</span>
                <span className="text-dark-400">{(filterSettings.min_score * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={80}
                value={filterSettings.min_score * 100}
                onChange={(e) => setFilterSettings({ min_score: Number(e.target.value) / 100 })}
                className="w-full h-1.5 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-dark-700 flex justify-between">
          <button
            onClick={() => {
              setFilterSettings({ filter_by_genes: true, filter_by_diseases: false, filter_by_pathways: false, min_score: 0.3 });
              setTopK(5);
              setIncludeGraph(false);
              setIncludeSummary(true);
              setIncludeDesignAssistant(true);
            }}
            className="text-sm text-dark-400 hover:text-dark-200"
          >
            Reset
          </button>
          <button onClick={handleClose} className="btn-primary px-4 py-1.5 text-sm">
            Done
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// TOGGLE OPTION COMPONENT
// ════════════════════════════════════════════════════════════════════════════
function ToggleOption({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between p-3 rounded-lg bg-dark-800 cursor-pointer hover:bg-dark-750 transition-colors">
      <div>
        <div className="text-sm text-dark-200">{label}</div>
        <div className="text-xs text-dark-500">{description}</div>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-500 focus:ring-primary-500/50"
      />
    </label>
  );
}