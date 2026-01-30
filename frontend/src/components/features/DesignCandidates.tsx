import { motion } from 'framer-motion';
import { Sparkles, Lightbulb, ArrowRight } from 'lucide-react';
import type { DesignCandidate } from '@/types';

interface Props {
  candidates: DesignCandidate[];
}

export default function DesignCandidates({ candidates }: Props) {
  if (candidates.length === 0) return null;

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20">
          <Sparkles className="text-purple-400" size={18} />
        </div>
        <div>
          <h3 className="font-semibold text-dark-100">Design Candidates</h3>
          <p className="text-xs text-dark-400">Diverse research directions</p>
        </div>
      </div>

      <div className="space-y-3">
        {candidates.map((candidate, index) => (
          <motion.div
            key={candidate.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="p-3 rounded-lg bg-dark-800/50 hover:bg-dark-800 transition-colors cursor-pointer"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold">
                {index + 1}
              </div>
              
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-dark-100 text-sm truncate">
                  {candidate.name}
                </h4>
                
                <p className="text-xs text-dark-400 mt-1 line-clamp-2">
                  {candidate.justification}
                </p>
                
                {candidate.research_suggestion && (
                  <div className="flex items-start gap-2 mt-2 p-2 rounded bg-primary-500/10">
                    <Lightbulb size={14} className="text-primary-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-primary-300">
                      {candidate.research_suggestion}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <button className="w-full mt-4 py-2 text-sm text-dark-400 hover:text-dark-200 flex items-center justify-center gap-2 transition-colors">
        Explore all candidates
        <ArrowRight size={14} />
      </button>
    </div>
  );
}
