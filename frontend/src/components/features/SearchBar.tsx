import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import {
  Search,
  X,
  Image as ImageIcon,
  Dna,
  Settings,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Box,
  FileText,
  File,
} from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';
import Structure3DViewer from './Structure3DViewer';

export default function SearchBar() {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showStructureModal, setShowStructureModal] = useState(false);
  const [showArticleModal, setShowArticleModal] = useState(false);
  const [pdbContent, setPdbContent] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [articleContent, setArticleContent] = useState<string | null>(null);
  const [articleType, setArticleType] = useState<'txt' | 'pdf' | null>(null);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);

  const {
    query,
    setQuery,
    sequence,
    setSequence,
    imageFile,
    setImageFile,
    structureFile,
    setStructureFile,
    articleFile,
    setArticleFile,
    topK,
    setTopK,
    includeGraph,
    setIncludeGraph,
    search,
    isLoading,
    setShowSettingsModal,
  } = useSearchStore();

  // Generate image preview
  useEffect(() => {
    if (imageFile) {
      const url = URL.createObjectURL(imageFile);
      setImagePreview(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setImagePreview(null);
    }
  }, [imageFile]);

  // Read PDB content
  useEffect(() => {
    if (structureFile) {
      structureFile.text().then(content => setPdbContent(content));
    } else {
      setPdbContent(null);
    }
  }, [structureFile]);

  // Read Article content + Generate PDF preview
  useEffect(() => {
    if (articleFile) {
      const isPdf = articleFile.type === 'application/pdf' || articleFile.name.endsWith('.pdf');
      setArticleType(isPdf ? 'pdf' : 'txt');

      if (isPdf) {
        const url = URL.createObjectURL(articleFile);
        setPdfPreviewUrl(url);
        setArticleContent(null);
        return () => URL.revokeObjectURL(url);
      } else {
        setPdfPreviewUrl(null);
        articleFile.text().then(content => setArticleContent(content));
      }
    } else {
      setArticleContent(null);
      setArticleType(null);
      setPdfPreviewUrl(null);
    }
  }, [articleFile]);

  // Dropzones
  const imageDropzone = useDropzone({
    accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'] },
    maxFiles: 1,
    onDrop: (files) => setImageFile(files[0] || null),
  });

  const structureDropzone = useDropzone({
    accept: { 'chemical/x-pdb': ['.pdb'], 'application/octet-stream': ['.pdb'] },
    maxFiles: 1,
    onDrop: (files) => setStructureFile(files[0] || null),
  });

  const articleDropzone = useDropzone({
    accept: { 'text/plain': ['.txt'], 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    onDrop: (files) => setArticleFile(files[0] || null),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    search();
  };

  // Ouvrir le modal Article
  const openArticleModal = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowArticleModal(true);
  };

  // Supprimer l'article
  const removeArticle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setArticleFile(null);
  };

  // Taille carrée
  const SQUARE_SIZE = 250;

  return (
    <>
      <form onSubmit={handleSubmit}>
        <div className="card p-6">
          {/* Main Search Input */}
          <div className="flex gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-dark-400" size={20} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search for genes, diseases, proteins, pathways..."
                className="input-field pl-12"
              />
            </div>

            <motion.button
              type="submit"
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn-primary px-8 disabled:opacity-50"
            >
              {isLoading ? (
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                  <Search size={18} />
                </motion.div>
              ) : (
                <span className="flex items-center gap-2">
                  <Search size={18} />
                  Search
                </span>
              )}
            </motion.button>
          </div>

          {/* Toggle Advanced */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-dark-400 hover:text-dark-200"
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            Advanced Options
          </button>

          {/* Advanced Options */}
          <AnimatePresence>
            {showAdvanced && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-6 space-y-5">

                  {/* PROTEIN SEQUENCE INPUT - Full Width */}
                  <div>
                    <label className="flex items-center gap-2 text-sm font-medium text-dark-300 mb-2">
                      <Dna size={16} className="text-green-400" />
                      Protein Sequence (optional)
                    </label>
                    <textarea
                      value={sequence}
                      onChange={(e) => setSequence(e.target.value)}
                      placeholder="Paste protein sequence (FASTA format or raw sequence)..."
                      className="input-field h-20 font-mono text-sm"
                    />
                  </div>

                  {/* ═══════════════════════════════════════════════════════════
                      ROW 1: Article + Image - CARRÉS 250px, côte à côte
                      ═══════════════════════════════════════════════════════════ */}
                  <div className="grid grid-cols-2 gap-4">

                    {/* ─────────────────────────────────────────────────────────
                        ARTICLE INPUT - CARRÉ 250px
                        ───────────────────────────────────────────────────────── */}
                    <div>
                      <label className="flex items-center gap-2 text-sm font-medium text-dark-300 mb-2">
                        <FileText size={16} className="text-blue-400" />
                        Article (optional)
                      </label>

                      {articleFile ? (
                        <div
                          className="relative rounded-xl overflow-hidden border-2 border-blue-500/30 bg-dark-800 cursor-pointer"
                          style={{ height: SQUARE_SIZE }}
                          onClick={openArticleModal}
                        >
                          {/* Article Preview */}
                          <div className="w-full h-full">
                            {articleType === 'pdf' ? (
                              <PdfThumbnail pdfUrl={pdfPreviewUrl} />
                            ) : (
                              <div className="w-full h-full bg-gradient-to-b from-slate-100 to-slate-200 p-3">
                                <div className="w-full h-full bg-white rounded shadow-sm p-3 overflow-hidden">
                                  <p className="text-[9px] text-gray-700 font-mono leading-tight whitespace-pre-wrap">
                                    {articleContent?.slice(0, 800) || 'Loading...'}
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Overlay */}
                          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-dark-900 via-dark-900/95 to-transparent p-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2 flex-1 min-w-0">
                                {articleType === 'pdf' ? (
                                  <File size={14} className="text-red-400 flex-shrink-0" />
                                ) : (
                                  <FileText size={14} className="text-blue-400 flex-shrink-0" />
                                )}
                                <span className="text-xs text-white truncate">{articleFile.name}</span>
                              </div>
                              <div className="flex gap-1 ml-2">
                                <button
                                  type="button"
                                  onClick={openArticleModal}
                                  className="p-1.5 bg-dark-700/80 hover:bg-blue-500/50 rounded-lg transition-colors"
                                >
                                  <Maximize2 size={12} className="text-white" />
                                </button>
                                <button
                                  type="button"
                                  onClick={removeArticle}
                                  className="p-1.5 bg-dark-700/80 hover:bg-red-500/50 rounded-lg transition-colors"
                                >
                                  <X size={12} className="text-white" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div
                          {...articleDropzone.getRootProps()}
                          style={{ height: SQUARE_SIZE }}
                          className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${articleDropzone.isDragActive
                            ? 'border-blue-400 bg-blue-500/10'
                            : 'border-dark-700 hover:border-dark-500 hover:bg-dark-800/50'
                            }`}
                        >
                          <input {...articleDropzone.getInputProps()} />
                          <div className="text-center p-4">
                            <div className="w-14 h-14 rounded-full bg-blue-500/20 flex items-center justify-center mx-auto mb-3">
                              <FileText size={28} className="text-blue-400" />
                            </div>
                            <p className="text-sm text-dark-300 mb-1">Article</p>
                            <p className="text-xs text-dark-500">TXT or PDF</p>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* ─────────────────────────────────────────────────────────
                        IMAGE INPUT - CARRÉ 250px
                        ───────────────────────────────────────────────────────── */}
                    <div>
                      <label className="flex items-center gap-2 text-sm font-medium text-dark-300 mb-2">
                        <ImageIcon size={16} className="text-pink-400" />
                        Image (optional)
                      </label>

                      {imageFile && imagePreview ? (
                        <div
                          className="relative rounded-xl overflow-hidden border-2 border-pink-500/30 bg-dark-800"
                          style={{ height: SQUARE_SIZE }}
                        >
                          <img
                            src={imagePreview}
                            alt="Preview"
                            className="w-full h-full object-cover"
                          />
                          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-dark-900 via-dark-900/95 to-transparent p-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2 flex-1 min-w-0">
                                <ImageIcon size={14} className="text-pink-400 flex-shrink-0" />
                                <span className="text-xs text-white truncate">{imageFile.name}</span>
                              </div>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setImageFile(null);
                                }}
                                className="p-1.5 bg-dark-700/80 hover:bg-red-500/50 rounded-lg transition-colors ml-2"
                              >
                                <X size={12} className="text-white" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div
                          {...imageDropzone.getRootProps()}
                          style={{ height: SQUARE_SIZE }}
                          className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${imageDropzone.isDragActive
                            ? 'border-pink-400 bg-pink-500/10'
                            : 'border-dark-700 hover:border-dark-500 hover:bg-dark-800/50'
                            }`}
                        >
                          <input {...imageDropzone.getInputProps()} />
                          <div className="text-center p-4">
                            <div className="w-14 h-14 rounded-full bg-pink-500/20 flex items-center justify-center mx-auto mb-3">
                              <ImageIcon size={28} className="text-pink-400" />
                            </div>
                            <p className="text-sm text-dark-300 mb-1">Image</p>
                            <p className="text-xs text-dark-500">PNG, JPG, WebP</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ═══════════════════════════════════════════════════════════
                      ROW 2: 3D Structure - FULL WIDTH en bas
                      ═══════════════════════════════════════════════════════════ */}
                  <div>
                    <label className="flex items-center gap-2 text-sm font-medium text-dark-300 mb-2">
                      <Box size={16} className="text-purple-400" />
                      3D Structure (optional)
                    </label>

                    {structureFile && pdbContent ? (
                      <div className="relative h-[200px] rounded-xl overflow-hidden border-2 border-purple-500/30 bg-dark-900">
                        <MiniStructurePreview pdbContent={pdbContent} />
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-dark-900 via-dark-900/95 to-transparent p-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <Box size={14} className="text-purple-400 flex-shrink-0" />
                              <span className="text-xs text-white truncate">{structureFile.name}</span>
                            </div>
                            <div className="flex gap-1 ml-2">
                              <button
                                type="button"
                                onClick={() => setShowStructureModal(true)}
                                className="p-1.5 bg-dark-700/80 hover:bg-purple-500/50 rounded-lg transition-colors"
                              >
                                <Maximize2 size={12} className="text-white" />
                              </button>
                              <button
                                type="button"
                                onClick={() => setStructureFile(null)}
                                className="p-1.5 bg-dark-700/80 hover:bg-red-500/50 rounded-lg transition-colors"
                              >
                                <X size={12} className="text-white" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div
                        {...structureDropzone.getRootProps()}
                        className={`h-[200px] border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${structureDropzone.isDragActive
                          ? 'border-purple-400 bg-purple-500/10'
                          : 'border-dark-700 hover:border-dark-500 hover:bg-dark-800/50'
                          }`}
                      >
                        <input {...structureDropzone.getInputProps()} />
                        <div className="text-center p-4">
                          <div className="w-14 h-14 rounded-full bg-purple-500/20 flex items-center justify-center mx-auto mb-3">
                            <Box size={28} className="text-purple-400" />
                          </div>
                          <p className="text-sm text-dark-300 mb-1">3D Structure</p>
                          <p className="text-xs text-dark-500">PDB format</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Settings Row */}
                  <div className="flex flex-wrap items-center gap-6 pt-2">
                    <div className="flex items-center gap-3">
                      <label className="text-sm text-dark-400">Results:</label>
                      <select
                        value={topK}
                        onChange={(e) => setTopK(Number(e.target.value))}
                        className="px-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg text-sm"
                      >
                        {[3, 5, 10, 15, 20].map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                    </div>

                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={includeGraph}
                        onChange={(e) => setIncludeGraph(e.target.checked)}
                        className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500"
                      />
                      <span className="text-sm text-dark-400">Show graph</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => setShowSettingsModal(true)}
                      className="flex items-center gap-2 text-sm text-primary-400 hover:text-primary-300 ml-auto"
                    >
                      <Settings size={16} />
                      More Settings
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </form>

      {/* ═══════════════════════════════════════════════════════════════════
          ARTICLE FULLSCREEN MODAL - CORRIGÉ
          ═══════════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {showArticleModal && articleFile && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setShowArticleModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-4xl h-[85vh] bg-dark-900 rounded-xl overflow-hidden flex flex-col shadow-2xl border border-dark-700"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-dark-700 bg-dark-800">
                <div className="flex items-center gap-3">
                  {articleType === 'pdf' ? (
                    <div className="p-2 rounded-lg bg-red-500/20">
                      <File size={20} className="text-red-400" />
                    </div>
                  ) : (
                    <div className="p-2 rounded-lg bg-blue-500/20">
                      <FileText size={20} className="text-blue-400" />
                    </div>
                  )}
                  <div>
                    <p className="font-medium text-dark-100">{articleFile.name}</p>
                    <p className="text-xs text-dark-500">
                      {(articleFile.size / 1024).toFixed(1)} KB • {articleType?.toUpperCase()}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowArticleModal(false)}
                  className="p-2 hover:bg-dark-700 rounded-lg transition-colors"
                >
                  <X size={20} className="text-dark-400" />
                </button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-hidden">
                {articleType === 'pdf' && pdfPreviewUrl ? (
                  <iframe
                    src={pdfPreviewUrl}
                    className="w-full h-full border-0"
                    title="PDF Preview"
                  />
                ) : (
                  <div className="h-full overflow-auto p-6 bg-dark-950">
                    <pre className="text-sm text-dark-200 font-mono whitespace-pre-wrap leading-relaxed">
                      {articleContent || 'No content available'}
                    </pre>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ═══════════════════════════════════════════════════════════════════
          STRUCTURE FULLSCREEN MODAL
          ═══════════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {showStructureModal && pdbContent && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setShowStructureModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-4xl h-[80vh] bg-dark-900 rounded-xl overflow-hidden shadow-2xl border border-dark-700"
              onClick={(e) => e.stopPropagation()}
            >
              <Structure3DViewer
                pdbData={pdbContent}
                title={structureFile?.name || 'Structure'}
                onClose={() => setShowStructureModal(false)}
                isFullscreen={true}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PDF THUMBNAIL - Aperçu visuel de la première page
// ═══════════════════════════════════════════════════════════════════════════════
function PdfThumbnail({ pdfUrl }: { pdfUrl: string | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!pdfUrl) return;

    const loadPdf = async () => {
      try {
        setIsLoading(true);
        setError(false);

        if (window.pdfjsLib && canvasRef.current && containerRef.current) {
          const pdf = await window.pdfjsLib.getDocument(pdfUrl).promise;
          const page = await pdf.getPage(1);

          const canvas = canvasRef.current;
          const container = containerRef.current;
          const context = canvas.getContext('2d')!;

          const containerWidth = container.offsetWidth;
          const containerHeight = container.offsetHeight;

          const viewport = page.getViewport({ scale: 1 });
          const scale = Math.max(containerWidth / viewport.width, containerHeight / viewport.height);
          const scaledViewport = page.getViewport({ scale });

          canvas.width = containerWidth;
          canvas.height = containerHeight;

          const offsetX = (containerWidth - scaledViewport.width) / 2;
          const offsetY = (containerHeight - scaledViewport.height) / 2;

          context.fillStyle = '#ffffff';
          context.fillRect(0, 0, containerWidth, containerHeight);

          context.save();
          context.translate(offsetX, offsetY);

          await page.render({
            canvasContext: context,
            viewport: scaledViewport,
          }).promise;

          context.restore();
          setIsLoading(false);
        } else {
          setError(true);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('PDF render error:', err);
        setError(true);
        setIsLoading(false);
      }
    };

    const timer = setTimeout(loadPdf, 100);
    return () => clearTimeout(timer);
  }, [pdfUrl]);

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gradient-to-b from-slate-100 to-slate-200">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        >
          <File size={32} className="text-red-400" />
        </motion.div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full bg-gradient-to-b from-slate-100 to-slate-200 p-3">
        <div className="w-full h-full bg-white rounded shadow-lg flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-7 bg-red-500 flex items-center px-3">
            <span className="text-white text-xs font-bold">PDF</span>
          </div>
          <div className="mt-8 w-3/4 space-y-2">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="h-2 bg-gray-200 rounded"
                style={{ width: `${60 + Math.random() * 40}%` }}
              />
            ))}
          </div>
          <File size={24} className="absolute bottom-3 right-3 text-red-400/40" />
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full">
      <canvas ref={canvasRef} className="w-full h-full object-cover" />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Mini Structure Preview (3Dmol.js)
// ═══════════════════════════════════════════════════════════════════════════════
function MiniStructurePreview({ pdbContent }: { pdbContent: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const init = () => {
      if (!window.$3Dmol || !containerRef.current) {
        setTimeout(init, 100);
        return;
      }

      const container = containerRef.current;
      const rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        setTimeout(init, 100);
        return;
      }

      try {
        container.innerHTML = '';
        const viewer = window.$3Dmol.createViewer(container, {
          backgroundColor: '#0d1117',
          width: rect.width,
          height: rect.height,
        });

        viewer.addModel(pdbContent, 'pdb');
        viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        viewer.zoomTo();
        viewer.render();
        viewer.spin('y', 0.5);
        viewerRef.current = viewer;
        setIsLoaded(true);
      } catch (err) {
        console.error('Mini viewer error:', err);
      }
    };

    setTimeout(init, 100);
    return () => {
      if (viewerRef.current) {
        viewerRef.current.spin(false);
        viewerRef.current = null;
      }
    };
  }, [pdbContent]);

  return (
    <div className="relative w-full h-full">
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-900">
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
            <Box size={24} className="text-purple-400" />
          </motion.div>
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}

// Type declarations
declare global {
  interface Window {
    $3Dmol: any;
    pdfjsLib: any;
  }
}