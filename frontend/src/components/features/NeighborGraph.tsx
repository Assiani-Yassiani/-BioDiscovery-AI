import { useRef, useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Network, ZoomIn, ZoomOut, Maximize2, X } from 'lucide-react';
import type { NeighborGraph as NeighborGraphType, GraphNode } from '@/types';

interface Props {
  graph: NeighborGraphType;
  onNodeClick?: (nodeId: string) => void;
}

// Color mapping for node types
const nodeColors: Record<string, string> = {
  protein: '#10B981',
  article: '#6366F1',
  image: '#F59E0B',
  experiment: '#EC4899',
  structure: '#8B5CF6',
};

export default function NeighborGraph({ graph, onNodeClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 400, height: 300 });

  // Update canvas size based on fullscreen
  useEffect(() => {
    if (isFullscreen) {
      setCanvasSize({ width: window.innerWidth - 100, height: window.innerHeight - 200 });
    } else {
      setCanvasSize({ width: 400, height: 300 });
    }
  }, [isFullscreen]);

  // Calculate positions
  const calculatePositions = useCallback(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    const nodes = graph.nodes;
    const { width, height } = canvasSize;
    const centerX = width / 2;
    const centerY = height / 2;

    nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      const radius = Math.min(width, height) * 0.35;
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    });

    // Force simulation
    for (let iter = 0; iter < 50; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = positions[nodes[j].id].x - positions[nodes[i].id].x;
          const dy = positions[nodes[j].id].y - positions[nodes[i].id].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (isFullscreen ? 2000 : 500) / (dist * dist);

          positions[nodes[i].id].x -= (dx / dist) * force;
          positions[nodes[i].id].y -= (dy / dist) * force;
          positions[nodes[j].id].x += (dx / dist) * force;
          positions[nodes[j].id].y += (dy / dist) * force;
        }
      }

      for (const edge of graph.edges) {
        const source = positions[edge.source];
        const target = positions[edge.target];
        if (!source || !target) continue;

        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const idealDist = isFullscreen ? 150 : 80;
        const force = (dist - idealDist) * 0.1 * edge.strength;

        source.x += (dx / dist) * force;
        source.y += (dy / dist) * force;
        target.x -= (dx / dist) * force;
        target.y -= (dy / dist) * force;
      }

      const margin = isFullscreen ? 80 : 30;
      for (const node of nodes) {
        const pos = positions[node.id];
        pos.x = Math.max(margin, Math.min(width - margin, pos.x));
        pos.y = Math.max(margin, Math.min(height - margin, pos.y));
      }
    }

    return positions;
  }, [graph, canvasSize, isFullscreen]);

  // Draw graph
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const positions = calculatePositions();
    const { width, height } = canvasSize;

    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.scale(scale, scale);

    // Draw edges
    for (const edge of graph.edges) {
      const source = positions[edge.source];
      const target = positions[edge.target];
      if (!source || !target) continue;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = `rgba(100, 116, 139, ${edge.strength * 0.5})`;
      ctx.lineWidth = Math.max(1, edge.strength * (isFullscreen ? 4 : 3));
      ctx.stroke();
    }

    // Draw nodes
    for (const node of graph.nodes) {
      const pos = positions[node.id];
      if (!pos) continue;

      const color = nodeColors[node.type] || '#64748b';
      const radius = node.is_center ? (isFullscreen ? 24 : 16) : (isFullscreen ? 16 : 10);

      if (node.is_center) {
        const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, radius * 2);
        gradient.addColorStop(0, color + '40');
        gradient.addColorStop(1, color + '00');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius * 2, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = '#e2e8f0';
      ctx.font = `${isFullscreen ? '14' : '10'}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      const maxLen = isFullscreen ? 25 : 15;
      const label = node.label.length > maxLen ? node.label.slice(0, maxLen - 3) + '...' : node.label;
      ctx.fillText(label, pos.x, pos.y + radius + (isFullscreen ? 20 : 14));
    }

    ctx.restore();
  }, [graph, scale, calculatePositions, canvasSize, isFullscreen]);

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || !onNodeClick) return;

      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / scale;
      const y = (e.clientY - rect.top) / scale;

      const positions = calculatePositions();

      for (const node of graph.nodes) {
        const pos = positions[node.id];
        if (!pos) continue;

        const dx = x - pos.x;
        const dy = y - pos.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < (isFullscreen ? 25 : 15)) {
          onNodeClick(node.id);
          return;
        }
      }
    },
    [graph, scale, onNodeClick, calculatePositions, isFullscreen]
  );

  const GraphContent = () => (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20">
            <Network className="text-blue-400" size={isFullscreen ? 24 : 18} />
          </div>
          <div>
            <h3 className={`font-semibold text-dark-100 ${isFullscreen ? 'text-xl' : ''}`}>
              Neighbor Graph
            </h3>
            <p className={`text-dark-400 ${isFullscreen ? 'text-sm' : 'text-xs'}`}>
              {graph.nodes.length} nodes • {graph.edges.length} connections
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}
            className="p-1.5 rounded hover:bg-dark-700 transition-colors"
            title="Zoom Out"
          >
            <ZoomOut size={isFullscreen ? 20 : 16} className="text-dark-400" />
          </button>
          <button
            onClick={() => setScale((s) => Math.min(2, s + 0.2))}
            className="p-1.5 rounded hover:bg-dark-700 transition-colors"
            title="Zoom In"
          >
            <ZoomIn size={isFullscreen ? 20 : 16} className="text-dark-400" />
          </button>
          <button
            onClick={() => {
              setScale(1);
              setIsFullscreen(!isFullscreen);
            }}
            className="p-1.5 rounded hover:bg-dark-700 transition-colors"
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? (
              <X size={20} className="text-dark-400" />
            ) : (
              <Maximize2 size={16} className="text-dark-400" />
            )}
          </button>
        </div>
      </div>

      <div className="relative rounded-lg bg-dark-800/50 overflow-hidden">
        <canvas
          ref={canvasRef}
          width={canvasSize.width}
          height={canvasSize.height}
          onClick={handleCanvasClick}
          className="w-full cursor-pointer"
        />

        <div className={`absolute bottom-2 left-2 flex flex-wrap gap-2 ${isFullscreen ? 'gap-4' : ''}`}>
          {Object.entries(nodeColors).map(([type, color]) => (
            <div key={type} className={`flex items-center gap-1 ${isFullscreen ? 'text-sm' : 'text-xs'}`}>
              <div
                className={`rounded-full ${isFullscreen ? 'w-3 h-3' : 'w-2 h-2'}`}
                style={{ backgroundColor: color }}
              />
              <span className="text-dark-400 capitalize">{type}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );

  if (isFullscreen) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-dark-950/95 backdrop-blur-sm p-8"
        >
          <motion.div
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.9 }}
            className="w-full h-full"
          >
            <GraphContent />
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  }

  return (
    <div className="card p-4">
      <GraphContent />
    </div>
  );
}
