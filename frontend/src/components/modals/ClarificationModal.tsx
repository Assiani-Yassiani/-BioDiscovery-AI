/**
 * ClarificationModal - Architecture v2.1
 * 
 * Displays when divergence is detected between text and modality inputs.
 * Allows user to choose search strategy with countdown timeout.
 */

import { useState, useEffect } from 'react';
import { useSearchStore } from '@/stores/searchStore';
import type { ClarificationOption } from '@/types';

interface OptionInfo {
  id: ClarificationOption;
  label: string;
  description: string;
  icon: string;
  color: string;
}

const OPTIONS: OptionInfo[] = [
  {
    id: 'intersection',
    label: 'Intersection',
    description: 'Only results that match BOTH text and modality',
    icon: '∩',
    color: 'bg-blue-500 hover:bg-blue-600',
  },
  {
    id: 'text_priority',
    label: 'Text Priority',
    description: 'Prioritize text query over image/sequence',
    icon: '📝',
    color: 'bg-green-500 hover:bg-green-600',
  },
  {
    id: 'modal_priority',
    label: 'Modality Priority',
    description: 'Prioritize image/sequence over text query',
    icon: '🔬',
    color: 'bg-purple-500 hover:bg-purple-600',
  },
  {
    id: 'multi_track',
    label: 'Multi-Track (Default)',
    description: 'Search both independently and merge results',
    icon: '⚡',
    color: 'bg-amber-500 hover:bg-amber-600',
  },
];

export function ClarificationModal() {
  const {
    showClarificationModal,
    clarificationRequest,
    searchWithChoice,
    setShowClarificationModal,
  } = useSearchStore();

  const [countdown, setCountdown] = useState(10);
  const [selectedOption, setSelectedOption] = useState<ClarificationOption | null>(null);

  // Reset countdown when modal opens
  useEffect(() => {
    if (showClarificationModal && clarificationRequest) {
      setCountdown(clarificationRequest.timeout_seconds || 10);
      setSelectedOption(null);
    }
  }, [showClarificationModal, clarificationRequest]);

  // Countdown timer
  useEffect(() => {
    if (!showClarificationModal || countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [showClarificationModal, countdown]);

  const handleSelect = (option: ClarificationOption) => {
    setSelectedOption(option);
    searchWithChoice(option);
  };

  const handleClose = () => {
    // Use default choice on close
    const defaultChoice = clarificationRequest?.default_choice || 'multi_track';
    searchWithChoice(defaultChoice);
  };

  if (!showClarificationModal || !clarificationRequest) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-gray-800">
          <div 
            className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-1000"
            style={{ width: `${(countdown / (clarificationRequest.timeout_seconds || 10)) * 100}%` }}
          />
        </div>

        {/* Header */}
        <div className="px-6 pt-5 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-amber-500/20 rounded-full flex items-center justify-center">
                <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Search Strategy</h2>
                <p className="text-sm text-gray-400">
                  Divergence detected between inputs
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-mono">{countdown}s</span>
            </div>
          </div>
        </div>

        {/* Message */}
        <div className="px-6 pb-4">
          <p className="text-gray-300 text-sm">
            {clarificationRequest.message || 'Your text query and uploaded file seem to be about different topics. How would you like to search?'}
          </p>
        </div>

        {/* Context comparison */}
        {(clarificationRequest.context_modal?.length > 0 || clarificationRequest.context_text?.length > 0) && (
          <div className="px-6 pb-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              {clarificationRequest.context_modal?.length > 0 && (
                <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
                  <div className="text-purple-400 font-medium mb-2 flex items-center gap-2">
                    <span>🔬</span> Modality Context
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {clarificationRequest.context_modal.slice(0, 5).map((term, i) => (
                      <span key={i} className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">
                        {term}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {clarificationRequest.context_text?.length > 0 && (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                  <div className="text-green-400 font-medium mb-2 flex items-center gap-2">
                    <span>📝</span> Text Context
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {clarificationRequest.context_text.slice(0, 5).map((term, i) => (
                      <span key={i} className="px-2 py-0.5 bg-green-500/20 text-green-300 rounded text-xs">
                        {term}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Options */}
        <div className="px-6 pb-6">
          <div className="grid grid-cols-2 gap-3">
            {OPTIONS.map((option) => (
              <button
                key={option.id}
                onClick={() => handleSelect(option.id)}
                disabled={selectedOption !== null}
                className={`
                  relative p-4 rounded-lg border-2 text-left transition-all
                  ${selectedOption === option.id 
                    ? 'border-amber-500 bg-amber-500/20' 
                    : 'border-gray-700 hover:border-gray-600 bg-gray-800/50 hover:bg-gray-800'
                  }
                  ${selectedOption !== null && selectedOption !== option.id ? 'opacity-50' : ''}
                  disabled:cursor-not-allowed
                `}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{option.icon}</span>
                  <div>
                    <div className="font-medium text-white flex items-center gap-2">
                      {option.label}
                      {clarificationRequest.default_choice === option.id && (
                        <span className="text-xs px-1.5 py-0.5 bg-amber-500/30 text-amber-400 rounded">
                          Default
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {option.description}
                    </p>
                  </div>
                </div>
                {selectedOption === option.id && (
                  <div className="absolute top-2 right-2">
                    <svg className="w-5 h-5 text-amber-500 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-800/50 border-t border-gray-700 flex justify-between items-center">
          <p className="text-xs text-gray-500">
            Auto-selecting "{clarificationRequest.default_choice}" in {countdown}s
          </p>
          <button
            onClick={handleClose}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Use default
          </button>
        </div>
      </div>
    </div>
  );
}

export default ClarificationModal;
