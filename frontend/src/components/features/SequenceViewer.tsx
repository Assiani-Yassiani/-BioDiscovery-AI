import { useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';
import toast from 'react-hot-toast';

interface Props {
  sequence: string;
  geneNames?: string[];
  maxDisplayLength?: number;
}

// Amino acid color scheme
const AA_COLORS: Record<string, string> = {
  // Hydrophobic (green)
  A: '#22c55e', I: '#22c55e', L: '#22c55e', M: '#22c55e', 
  F: '#22c55e', V: '#22c55e', W: '#22c55e',
  // Polar (blue)
  S: '#3b82f6', T: '#3b82f6', N: '#3b82f6', Q: '#3b82f6',
  // Acidic (red)
  D: '#ef4444', E: '#ef4444',
  // Basic (purple)
  K: '#8b5cf6', R: '#8b5cf6', H: '#8b5cf6',
  // Special (yellow)
  C: '#eab308', G: '#eab308', P: '#eab308', Y: '#eab308',
  // Unknown
  X: '#6b7280',
};

export default function SequenceViewer({ 
  sequence, 
  geneNames,
  maxDisplayLength = 500 
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const displaySequence = expanded 
    ? sequence 
    : sequence.slice(0, maxDisplayLength);

  const handleCopy = () => {
    navigator.clipboard.writeText(sequence);
    setCopied(true);
    toast.success('Sequence copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg bg-dark-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-dark-700/50 border-b border-dark-600">
        <div className="flex items-center gap-3">
          {geneNames && geneNames.length > 0 && (
            <span className="text-sm font-medium text-dark-200">
              {geneNames[0]}
            </span>
          )}
          <span className="text-xs text-dark-400">
            {sequence.length} amino acids
          </span>
        </div>
        
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-600 transition-colors"
        >
          {copied ? (
            <>
              <Check size={12} className="text-green-400" />
              Copied
            </>
          ) : (
            <>
              <Copy size={12} />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Sequence Display */}
      <div className="p-4 max-h-48 overflow-y-auto">
        <div className="font-mono text-xs leading-relaxed break-all">
          {displaySequence.split('').map((aa, index) => (
            <motion.span
              key={index}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: Math.min(index * 0.001, 0.5) }}
              style={{ color: AA_COLORS[aa.toUpperCase()] || '#6b7280' }}
              className="hover:bg-dark-600 cursor-default"
              title={`Position ${index + 1}: ${aa}`}
            >
              {aa}
            </motion.span>
          ))}
          {!expanded && sequence.length > maxDisplayLength && (
            <span className="text-dark-500">...</span>
          )}
        </div>
      </div>

      {/* Expand/Collapse */}
      {sequence.length > maxDisplayLength && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-4 py-2 flex items-center justify-center gap-2 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-700/50 transition-colors border-t border-dark-600"
        >
          {expanded ? (
            <>
              <ChevronUp size={14} />
              Show less
            </>
          ) : (
            <>
              <ChevronDown size={14} />
              Show full sequence ({sequence.length - maxDisplayLength} more)
            </>
          )}
        </button>
      )}

      {/* Legend */}
      <div className="px-4 py-2 flex flex-wrap gap-3 text-xs border-t border-dark-600">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          Hydrophobic
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          Polar
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          Acidic
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          Basic
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          Special
        </span>
      </div>
    </div>
  );
}
