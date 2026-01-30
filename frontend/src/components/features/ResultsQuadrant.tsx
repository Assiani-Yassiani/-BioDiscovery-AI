import { motion } from 'framer-motion';
import { Dna, FileText, Image, FlaskConical, Atom } from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';
import ResultCard from './ResultCard';
import type { CollectionType, TabItem } from '@/types';

const TABS: TabItem[] = [
  { id: 'proteins', label: 'Proteins', icon: 'dna', color: 'protein' },
  { id: 'articles', label: 'Articles', icon: 'file-text', color: 'article' },
  { id: 'images', label: 'Images', icon: 'image', color: 'image' },
  { id: 'experiments', label: 'Experiments', icon: 'flask', color: 'experiment' },
  { id: 'structures', label: 'Structures', icon: 'atom', color: 'structure' },
];

const iconMap = {
  dna: Dna,
  'file-text': FileText,
  image: Image,
  flask: FlaskConical,
  atom: Atom,
};

export default function ResultsQuadrant() {
  const { results, activeTab, setActiveTab } = useSearchStore();

  if (!results) return null;

  const quadrant = results.quadrant;

  // Add counts to tabs
  const tabsWithCounts = TABS.map((tab) => ({
    ...tab,
    count: quadrant[tab.id].length,
  }));

  const activeResults = quadrant[activeTab];

  return (
    <div className="card overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-dark-700 overflow-x-auto no-scrollbar">
        {tabsWithCounts.map((tab) => {
          const Icon = iconMap[tab.icon as keyof typeof iconMap];
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors relative ${
                isActive
                  ? `text-bio-${tab.color}`
                  : 'text-dark-400 hover:text-dark-200'
              }`}
            >
              <Icon size={16} />
              {tab.label}
              {tab.count > 0 && (
                <span
                  className={`px-1.5 py-0.5 text-xs rounded-full ${
                    isActive
                      ? `bg-bio-${tab.color}/20`
                      : 'bg-dark-700'
                  }`}
                >
                  {tab.count}
                </span>
              )}
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className={`absolute bottom-0 left-0 right-0 h-0.5 bg-bio-${tab.color}`}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Results */}
      <div className="p-4 max-h-[600px] overflow-y-auto">
        {activeResults.length > 0 ? (
          <div className="space-y-4">
            {activeResults.map((result, index) => (
              <motion.div
                key={result.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <ResultCard result={result} />
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-dark-400">
            No {activeTab} found for this query
          </div>
        )}
      </div>
    </div>
  );
}
