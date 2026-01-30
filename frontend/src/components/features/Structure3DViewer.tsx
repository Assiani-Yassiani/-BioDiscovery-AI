import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { X, RotateCcw, ZoomIn, ZoomOut, Box, Maximize2 } from 'lucide-react';

declare global {
  interface Window {
    $3Dmol: any;
  }
}

interface Structure3DViewerProps {
  pdbData?: string;
  pdbUrl?: string;
  pdbId?: string;
  title?: string;
  onClose?: () => void;
  isFullscreen?: boolean;
}

export default function Structure3DViewer({
  pdbData,
  pdbUrl,
  pdbId,
  title,
  onClose,
  isFullscreen = false,
}: Structure3DViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [style, setStyle] = useState<'cartoon' | 'stick' | 'sphere' | 'surface'>('cartoon');
  const [scriptLoaded, setScriptLoaded] = useState(false);

  // Load 3Dmol.js script
  useEffect(() => {
    if (window.$3Dmol) {
      setScriptLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://3dmol.org/build/3Dmol-min.js';
    script.async = true;
    script.onload = () => {
      setScriptLoaded(true);
    };
    script.onerror = () => {
      setError('Failed to load 3Dmol.js library');
      setIsLoading(false);
    };
    document.head.appendChild(script);

    return () => {
      // Don't remove script on unmount
    };
  }, []);

  // Initialize viewer when script is loaded and container is ready
  useEffect(() => {
    if (!scriptLoaded || !containerRef.current) return;

    // Wait for container to have dimensions
    const initViewer = () => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        // Retry after a short delay
        setTimeout(initViewer, 100);
        return;
      }

      try {
        // Clear previous viewer
        if (viewerRef.current) {
          viewerRef.current = null;
        }
        container.innerHTML = '';

        // Create viewer with explicit dimensions
        const viewer = window.$3Dmol.createViewer(container, {
          backgroundColor: '#1a1a2e',
          width: rect.width,
          height: rect.height,
        });

        viewerRef.current = viewer;
        loadStructure(viewer);
      } catch (err) {
        console.error('Error creating viewer:', err);
        setError('Failed to create 3D viewer');
        setIsLoading(false);
      }
    };

    // Small delay to ensure container is rendered
    setTimeout(initViewer, 200);

    return () => {
      if (viewerRef.current) {
        viewerRef.current = null;
      }
    };
  }, [scriptLoaded, pdbData, pdbUrl, pdbId]);

  const loadStructure = async (viewer: any) => {
    setIsLoading(true);
    setError(null);

    try {
      let data = pdbData;

      if (!data && pdbUrl) {
        const response = await fetch(pdbUrl);
        data = await response.text();
      }

      if (!data && pdbId) {
        const response = await fetch(`https://files.rcsb.org/download/${pdbId}.pdb`);
        data = await response.text();
      }

      if (!data) {
        setError('No structure data provided');
        setIsLoading(false);
        return;
      }

      viewer.addModel(data, 'pdb');
      applyStyle(viewer, style);
      viewer.zoomTo();
      viewer.render();
      setIsLoading(false);
    } catch (err) {
      console.error('Error loading structure:', err);
      setError('Failed to load structure');
      setIsLoading(false);
    }
  };

  const applyStyle = (viewer: any, styleName: string) => {
    viewer.setStyle({}, {});

    switch (styleName) {
      case 'cartoon':
        viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        break;
      case 'stick':
        viewer.setStyle({}, { stick: { colorscheme: 'Jmol' } });
        break;
      case 'sphere':
        viewer.setStyle({}, { sphere: { colorscheme: 'Jmol', scale: 0.3 } });
        break;
      case 'surface':
        viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        viewer.addSurface(window.$3Dmol.SurfaceType.VDW, { opacity: 0.7, color: 'white' });
        break;
    }

    viewer.render();
  };

  const changeStyle = (newStyle: 'cartoon' | 'stick' | 'sphere' | 'surface') => {
    setStyle(newStyle);
    if (viewerRef.current) {
      viewerRef.current.removeAllSurfaces();
      applyStyle(viewerRef.current, newStyle);
    }
  };

  const resetView = () => {
    if (viewerRef.current) {
      viewerRef.current.zoomTo();
      viewerRef.current.render();
    }
  };

  const zoom = (factor: number) => {
    if (viewerRef.current) {
      viewerRef.current.zoom(factor);
      viewerRef.current.render();
    }
  };

  return (
    <div className={`flex flex-col bg-dark-900 rounded-lg overflow-hidden ${isFullscreen ? 'h-full' : 'h-[400px]'}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 bg-dark-800 border-b border-dark-700">
        <div className="flex items-center gap-2">
          <Box size={18} className="text-primary-400" />
          <span className="font-medium text-sm">{title || 'Structure Viewer'}</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Style buttons */}
          {['cartoon', 'stick', 'sphere', 'surface'].map((s) => (
            <button
              key={s}
              onClick={() => changeStyle(s as any)}
              className={`px-2 py-1 text-xs rounded ${style === s
                ? 'bg-primary-500 text-white'
                : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
                }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}

          <div className="w-px h-4 bg-dark-600 mx-1" />

          {/* Control buttons */}
          <button onClick={() => zoom(1.2)} className="p-1.5 hover:bg-dark-700 rounded" title="Zoom In">
            <ZoomIn size={16} className="text-dark-300" />
          </button>
          <button onClick={() => zoom(0.8)} className="p-1.5 hover:bg-dark-700 rounded" title="Zoom Out">
            <ZoomOut size={16} className="text-dark-300" />
          </button>
          <button onClick={resetView} className="p-1.5 hover:bg-dark-700 rounded" title="Reset View">
            <RotateCcw size={16} className="text-dark-300" />
          </button>

          {onClose && (
            <button onClick={onClose} className="p-1.5 hover:bg-dark-700 rounded ml-2" title="Close">
              <X size={16} className="text-dark-300" />
            </button>
          )}
        </div>
      </div>

      {/* Viewer Container */}
      <div className="flex-1 relative" style={{ minHeight: '300px' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-dark-900/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Box size={24} className="text-primary-400" />
              </motion.div>
              <span className="text-sm text-dark-400">Loading structure...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-dark-900">
            <div className="text-center p-4">
              <p className="text-red-400 mb-2">{error}</p>
              <p className="text-dark-500 text-sm">Make sure the PDB data is valid</p>
            </div>
          </div>
        )}

        <div
          ref={containerRef}
          className="w-full h-full"
          style={{ minHeight: '300px', minWidth: '300px' }}
        />
      </div>
    </div>
  );
}