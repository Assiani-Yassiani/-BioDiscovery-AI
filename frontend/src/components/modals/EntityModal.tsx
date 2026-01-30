import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, ExternalLink, Copy, Dna, Link2, Atom,
  Image as ImageIcon, FlaskConical, ChevronDown,
  FileText, Globe, AlertCircle
} from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';
import Structure3DViewer from '@/components/features/Structure3DViewer';
import toast from 'react-hot-toast';

const BACKEND_URL = 'http://localhost:8000';

// ════════════════════════════════════════════════════════════════════════════════
// Convert local file path → backend static URL
// ════════════════════════════════════════════════════════════════════════════════
function getStaticUrl(filePath: string): string | null {
  if (!filePath) return null;

  const filename = filePath.split('\\').pop() || filePath.split('/').pop();
  if (!filename) return null;

  // PDB
  if (filePath.includes('structures_pdb') || (filePath.endsWith('.pdb') && !filePath.includes('alphafold'))) {
    return `${BACKEND_URL}/static/pdb/${filename}`;
  }
  // AlphaFold
  if (filePath.includes('alphafold') || filePath.includes('structures_alphafold')) {
    return `${BACKEND_URL}/static/alphafold/${filename}`;
  }
  // Images (KEGG, HPA, all images)
  if (filePath.includes('images') || filePath.match(/\.(png|jpg|jpeg|gif|webp)$/i)) {
    return `${BACKEND_URL}/static/images/${filename}`;
  }

  return null;
}

const COLLECTION_COLORS = {
  proteins: { bg: 'bg-bio-protein/10', border: 'border-bio-protein/30', text: 'text-bio-protein' },
  articles: { bg: 'bg-bio-article/10', border: 'border-bio-article/30', text: 'text-bio-article' },
  images: { bg: 'bg-bio-image/10', border: 'border-bio-image/30', text: 'text-bio-image' },
  experiments: { bg: 'bg-bio-experiment/10', border: 'border-bio-experiment/30', text: 'text-bio-experiment' },
  structures: { bg: 'bg-bio-structure/10', border: 'border-bio-structure/30', text: 'text-bio-structure' },
};

export default function EntityModal() {
  const { selectedEntity, setSelectedEntity, setShowEntityModal } = useSearchStore();

  const [showStructure, setShowStructure] = useState(false);
  const [showImage, setShowImage] = useState(false);
  const [showExperiment, setShowExperiment] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    setShowStructure(false);
    setShowImage(false);
    setShowExperiment(false);
    setImageLoaded(false);
    setImageError(false);
  }, [selectedEntity]);

  if (!selectedEntity) return null;

  const { payload, collection } = selectedEntity;
  const bridge = payload.normalized_bridge || {};
  const colors = COLLECTION_COLORS[collection] || COLLECTION_COLORS.proteins;

  const handleClose = () => {
    setSelectedEntity(null);
    setShowEntityModal(false);
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied!`, { duration: 2000 });
  };

  // ════════════════════════════════════════════════════════════════════════════════
  // IMAGE URL - Same logic for KEGG and HPA
  // file_path → local image
  // url → external link
  // ════════════════════════════════════════════════════════════════════════════════

  const localImageUrl = payload.file_path ? getStaticUrl(payload.file_path) : null;
  const externalUrl = payload.url || null;

  // Structure URL
  const getStructureUrl = (): string | null => {
    if (payload.pdb_id) return `https://files.rcsb.org/download/${payload.pdb_id}.pdb`;
    if (payload.file_path && collection === 'structures') return getStaticUrl(payload.file_path);
    if (payload.alphafold_id) {
      const match = payload.alphafold_id.match(/AF-([A-Z0-9]+)-/i);
      if (match) return `${BACKEND_URL}/static/alphafold/${match[1]}.pdb`;
    }
    if (payload.uniprot_ids?.[0]) return `${BACKEND_URL}/static/alphafold/${payload.uniprot_ids[0]}.pdb`;
    return null;
  };

  const structureUrl = getStructureUrl();

  const canShowStructure = collection === 'structures' && structureUrl;
  const canShowImage = collection === 'images' && (localImageUrl || externalUrl);
  const canShowExperiment = collection === 'experiments' && payload.measurements?.length > 0;

  // ════════════════════════════════════════════════════════════════════════════════
  // EXTERNAL LINKS
  // ════════════════════════════════════════════════════════════════════════════════

  const getExternalLinks = () => {
    const links: Array<{ label: string; url: string }> = [];

    if (collection === 'proteins') {
      if (payload.uniprot_id) {
        links.push({ label: 'UniProt', url: `https://www.uniprot.org/uniprotkb/${payload.uniprot_id}` });
        links.push({ label: 'AlphaFold', url: `https://alphafold.ebi.ac.uk/entry/${payload.uniprot_id}` });
      }
    }
    if (collection === 'articles') {
      if (payload.pmid) links.push({ label: 'PubMed', url: `https://pubmed.ncbi.nlm.nih.gov/${payload.pmid}` });
      if (payload.doi) links.push({ label: 'DOI', url: `https://doi.org/${payload.doi}` });
    }
    if (collection === 'structures') {
      if (payload.pdb_id) links.push({ label: 'RCSB PDB', url: `https://www.rcsb.org/structure/${payload.pdb_id}` });
    }
    if (collection === 'experiments' && payload.accession) {
      links.push({ label: 'GEO', url: `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${payload.accession}` });
    }
    if (collection === 'images' && externalUrl) {
      // Label based on source
      const label = payload.source === 'HPA' ? 'View on HPA' :
        payload.source === 'kegg' || payload.source === 'KEGG' ? 'KEGG Pathway' :
          'Original Source';
      links.push({ label, url: externalUrl });
    }

    return links;
  };

  const externalLinks = getExternalLinks();

  // Expandable Section
  const ExpandableSection = ({ show, onToggle, icon: Icon, label, color, children }: any) => (
    <div className={`rounded-xl overflow-hidden border ${show ? 'border-dark-600' : 'border-dark-700'}`}>
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between p-4 ${show ? 'bg-dark-800' : 'bg-dark-850 hover:bg-dark-800'}`}
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${color}`}><Icon size={18} /></div>
          <span className="font-medium text-dark-200">{label}</span>
        </div>
        <motion.div animate={{ rotate: show ? 180 : 0 }}>
          <ChevronDown size={18} className="text-dark-400" />
        </motion.div>
      </button>
      <AnimatePresence>
        {show && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 20 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-3xl max-h-[90vh] bg-dark-900 rounded-2xl overflow-hidden flex flex-col shadow-2xl border border-dark-700"
        >
          {/* HEADER */}
          <div className={`p-6 border-b border-dark-700 ${colors.bg}`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} border ${colors.border}`}>
                    {collection === 'proteins' && <Dna size={12} />}
                    {collection === 'articles' && <FileText size={12} />}
                    {collection === 'images' && <ImageIcon size={12} />}
                    {collection === 'experiments' && <FlaskConical size={12} />}
                    {collection === 'structures' && <Atom size={12} />}
                    {collection}
                  </span>
                  {payload.source && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-dark-800 text-dark-300">
                      <Globe size={10} />{payload.source}
                    </span>
                  )}
                  {payload.image_type && (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-dark-800 text-dark-400">{payload.image_type}</span>
                  )}
                </div>

                <h2 className="text-xl font-bold text-white mb-1">
                  {payload.protein_name || payload.title || payload.caption || payload.accession || 'Details'}
                </h2>

                {payload.gene_names?.length > 0 && (
                  <p className="text-dark-400 text-sm">{payload.gene_names.join(', ')}</p>
                )}
                {payload.gene_name && !payload.gene_names && (
                  <p className="text-dark-400 text-sm">Gene: {payload.gene_name}</p>
                )}

                <div className="flex flex-wrap gap-2 mt-2">
                  {payload.pdb_id && <span className="text-xs px-2 py-0.5 rounded bg-dark-800 text-dark-300">PDB: {payload.pdb_id}</span>}
                  {payload.uniprot_id && <span className="text-xs px-2 py-0.5 rounded bg-dark-800 text-dark-300">UniProt: {payload.uniprot_id}</span>}
                  {payload.ensembl_id && <span className="text-xs px-2 py-0.5 rounded bg-dark-800 text-dark-300">{payload.ensembl_id}</span>}
                </div>
              </div>
              <button onClick={handleClose} className="p-2 rounded-xl hover:bg-dark-800/50">
                <X size={20} className="text-dark-400" />
              </button>
            </div>
          </div>

          {/* CONTENT */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">

            {/* 3D Structure */}
            {canShowStructure && (
              <ExpandableSection show={showStructure} onToggle={() => setShowStructure(!showStructure)} icon={Atom} label="3D Structure" color="bg-bio-structure/20 text-bio-structure">
                <div className="h-[400px]">
                  <Structure3DViewer pdbId={payload.pdb_id || payload.alphafold_id} pdbUrl={structureUrl!} title={payload.title || 'Structure'} />
                </div>
              </ExpandableSection>
            )}

            {/* ═══════════════════════════════════════════════════════════════
                IMAGE - Same for KEGG and HPA
                ═══════════════════════════════════════════════════════════════ */}
            {canShowImage && (
              <ExpandableSection show={showImage} onToggle={() => setShowImage(!showImage)} icon={ImageIcon} label="Image" color="bg-bio-image/20 text-bio-image">
                <div className="p-4 bg-dark-950">

                  {/* LOCAL IMAGE (file_path exists) */}
                  {localImageUrl && (
                    <>
                      {!imageLoaded && !imageError && (
                        <div className="h-48 flex items-center justify-center">
                          <div className="animate-pulse text-dark-500">Loading image...</div>
                        </div>
                      )}

                      <img
                        src={localImageUrl}
                        alt={payload.caption || 'Image'}
                        className={`max-h-[400px] mx-auto object-contain rounded-lg ${imageLoaded ? 'block' : 'hidden'}`}
                        onLoad={() => setImageLoaded(true)}
                        onError={() => setImageError(true)}
                      />

                      {imageError && (
                        <div className="flex flex-col items-center justify-center py-8 gap-4">
                          <AlertCircle size={32} className="text-red-400" />
                          <p className="text-red-400">Failed to load local image</p>
                          <p className="text-dark-500 text-xs">Check that file exists: {payload.file_path}</p>
                          {externalUrl && (
                            <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-bio-image/20 text-bio-image">
                              <ExternalLink size={16} />Open on {payload.source || 'website'}
                            </a>
                          )}
                        </div>
                      )}

                      {/* Link to external even when local works */}
                      {imageLoaded && externalUrl && (
                        <div className="mt-4 flex justify-center">
                          <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 text-dark-300 text-sm">
                            <ExternalLink size={14} />View on {payload.source || 'source'}
                          </a>
                        </div>
                      )}
                    </>
                  )}

                  {/* NO LOCAL - External only */}
                  {!localImageUrl && externalUrl && (
                    <div className="flex flex-col items-center justify-center py-8 gap-4">
                      <div className="w-16 h-16 rounded-full bg-bio-image/20 flex items-center justify-center">
                        <Globe size={32} className="text-bio-image" />
                      </div>
                      <p className="text-dark-300">No local image - view on external site</p>
                      <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-bio-image hover:bg-bio-image/80 text-white font-medium">
                        <ExternalLink size={18} />Open on {payload.source || 'Website'}
                      </a>
                    </div>
                  )}
                </div>
              </ExpandableSection>
            )}

            {/* Experiment */}
            {canShowExperiment && (
              <ExpandableSection show={showExperiment} onToggle={() => setShowExperiment(!showExperiment)} icon={FlaskConical} label={`Measurements (${payload.measurements.length})`} color="bg-bio-experiment/20 text-bio-experiment">
                <div className="p-4 bg-dark-950 max-h-[300px] overflow-y-auto space-y-2">
                  {payload.measurements.map((m: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-dark-800">
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-dark-500 w-20 font-mono">{m.sample_id}</span>
                        <span className="text-sm text-dark-300">{m.condition}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-dark-400 font-mono">FC: {m.fold_change?.toFixed(2)}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.label === 'upregulated' ? 'bg-green-500/20 text-green-400' : m.label === 'downregulated' ? 'bg-red-500/20 text-red-400' : 'bg-dark-700 text-dark-400'}`}>
                          {m.label}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </ExpandableSection>
            )}

            {/* Description */}
            {(payload.function || payload.abstract || payload.description || payload.summary) && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-dark-300">Description</h4>
                <p className="text-dark-400 text-sm leading-relaxed bg-dark-800/50 p-4 rounded-xl">
                  {payload.function || payload.abstract || payload.description || payload.summary}
                </p>
              </div>
            )}

            {/* HPA Location */}
            {payload.location && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-dark-300">Subcellular Location</h4>
                <p className="text-dark-400 text-sm bg-dark-800/50 p-4 rounded-xl">{payload.location}</p>
              </div>
            )}

            {/* Metadata */}
            {(payload.method || payload.resolution || payload.cell_line || payload.antibody_id || payload.experiment_type) && (
              <div className="grid grid-cols-2 gap-3">
                {payload.method && <MetadataCard label="Method" value={payload.method} />}
                {payload.resolution && <MetadataCard label="Resolution" value={`${payload.resolution} Å`} />}
                {payload.cell_line && <MetadataCard label="Cell Line" value={payload.cell_line} />}
                {payload.antibody_id && <MetadataCard label="Antibody" value={payload.antibody_id} />}
                {payload.experiment_type && <MetadataCard label="Type" value={payload.experiment_type} />}
                {payload.organism && <MetadataCard label="Organism" value={payload.organism} />}
              </div>
            )}

            {/* Sequence */}
            {payload.sequence && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-dark-300 flex items-center gap-2">
                    <Dna size={14} />Sequence ({payload.sequence?.length || 0} aa)
                  </h4>
                  <button onClick={() => copyToClipboard(payload.sequence, 'Sequence')} className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1">
                    <Copy size={12} /> Copy
                  </button>
                </div>
                <div className="p-3 rounded-xl bg-dark-800 font-mono text-xs text-dark-400 break-all max-h-24 overflow-y-auto">{payload.sequence}</div>
              </div>
            )}

            {/* Related Entities */}
            {(bridge.genes?.length > 0 || bridge.diseases?.length > 0 || bridge.pathways?.length > 0) && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-dark-300">Related Entities</h4>
                <div className="flex flex-wrap gap-2">
                  {bridge.genes?.map((g: string) => <span key={g} className="badge-protein">{g}</span>)}
                  {bridge.diseases?.map((d: string) => <span key={d} className="badge-article">{d}</span>)}
                  {bridge.pathways?.map((p: string) => <span key={p} className="badge-image">{p}</span>)}
                </div>
              </div>
            )}

            {/* External Links */}
            {externalLinks.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-dark-300 flex items-center gap-2"><Link2 size={14} /> External Links</h4>
                <div className="flex flex-wrap gap-2">
                  {externalLinks.map((link) => (
                    <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-sm text-primary-400 hover:text-primary-300">
                      {link.label}<ExternalLink size={12} />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* File Path */}
            {payload.file_path && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-dark-300">Local File</h4>
                <div className="flex items-center gap-2 p-3 rounded-xl bg-dark-800">
                  <code className="text-xs text-dark-400 flex-1 truncate">{payload.file_path}</code>
                  <button onClick={() => copyToClipboard(payload.file_path, 'Path')} className="p-1.5 hover:bg-dark-700 rounded-lg">
                    <Copy size={14} className="text-dark-400" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-dark-700 flex justify-end">
            <button onClick={handleClose} className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-dark-200">Close</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function MetadataCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-3 rounded-xl bg-dark-800/50">
      <div className="text-xs text-dark-500 mb-1">{label}</div>
      <div className="text-sm text-dark-200">{value}</div>
    </div>
  );
}