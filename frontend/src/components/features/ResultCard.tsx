import { motion } from 'framer-motion';
import { ExternalLink, TrendingUp, Sparkles, Eye } from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';
import { api } from '@/services/api';
import type { ResultItem } from '@/types';

interface Props {
  result: ResultItem;
}

export default function ResultCard({ result }: Props) {
  const { setSelectedEntity, setShowEntityModal } = useSearchStore();

  const handleClick = async () => {
    try {
      const details = await api.getEntityDetails(result.collection, result.id);
      setSelectedEntity(details);
      setShowEntityModal(true);
    } catch (error) {
      console.error('Failed to fetch entity details:', error);
    }
  };

  const bridge = result.payload.normalized_bridge || {};
  const evidence = result.evidence;

  // Get collection-specific display info
  const getDisplayInfo = () => {
    const p = result.payload;
    
    switch (result.collection) {
      case 'proteins':
        return {
          subtitle: p.gene_names?.join(', ') || '',
          meta: `${p.organism || 'Unknown'} • ${p.sequence_length || 0} aa`,
        };
      case 'articles':
        return {
          subtitle: p.journal || '',
          meta: `${p.year || ''} • PMID: ${p.pmid || ''}`,
        };
      case 'images':
        return {
          subtitle: p.source || '',
          meta: p.image_type || '',
        };
      case 'experiments':
        return {
          subtitle: p.data_type || '',
          meta: `${p.n_samples || 0} samples • ${p.accession || ''}`,
        };
      case 'structures':
        return {
          subtitle: p.method || 'Unknown',
          meta: p.pdb_id || p.alphafold_id || '',
        };
      default:
        return { subtitle: '', meta: '' };
    }
  };

  const displayInfo = getDisplayInfo();

  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      onClick={handleClick}
      className="card-hover p-4 cursor-pointer relative overflow-hidden"
    >
      {/* Collection Indicator */}
      <div className={`result-indicator-${result.collection}`} />

      <div className="pl-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-dark-100 truncate">{result.name}</h3>
            {displayInfo.subtitle && (
              <p className="text-sm text-dark-400 truncate">{displayInfo.subtitle}</p>
            )}
          </div>
          
          {/* Scores */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="text-right">
              <div className="text-sm font-medium text-dark-100">
                {(result.final_score ?? result.score * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-dark-500">score</div>
            </div>
          </div>
        </div>

        {/* Description */}
        {result.description && (
          <p className="text-sm text-dark-400 line-clamp-2 mb-3">
            {result.description}
          </p>
        )}

        {/* Meta & Tags */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {displayInfo.meta && (
            <span className="text-dark-500">{displayInfo.meta}</span>
          )}
          
          {bridge.genes?.slice(0, 3).map((gene: string) => (
            <span key={gene} className="badge-protein">
              {gene}
            </span>
          ))}
          
          {bridge.diseases?.slice(0, 2).map((disease: string) => (
            <span key={disease} className="badge-article">
              {disease}
            </span>
          ))}
        </div>

        {/* Bottom Bar */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-dark-700/50">
          {/* Diversity & Novelty Indicators */}
          <div className="flex items-center gap-4 text-xs">
            {result.diversity_score !== undefined && (
              <div className="flex items-center gap-1 text-dark-400">
                <TrendingUp size={12} />
                <span>Diversity: {(result.diversity_score * 100).toFixed(0)}%</span>
              </div>
            )}
            {result.novelty_score !== undefined && (
              <div className="flex items-center gap-1 text-dark-400">
                <Sparkles size={12} />
                <span>Novelty: {(result.novelty_score * 100).toFixed(0)}%</span>
              </div>
            )}
          </div>

          {/* Evidence & Actions */}
          <div className="flex items-center gap-3">
            {evidence && (
              <div className="flex items-center gap-1 text-xs text-dark-400">
                <span className="text-green-400">
                  {(evidence.confidence * 100).toFixed(0)}%
                </span>
                <span>confidence</span>
              </div>
            )}
            
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleClick();
              }}
              className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
            >
              <Eye size={12} />
              Details
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
