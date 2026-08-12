import React, { useState, useRef, useCallback } from "react";
import { WorkflowNodeCard } from "./WorkflowNodeCard";
import type { WorkflowNodeData } from "./WorkflowNodeCard";
import { X, AlertTriangle, Maximize2, Minimize2, ZoomIn, ZoomOut, Focus } from "lucide-react";

export interface WorkflowEdge {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
}

export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 2.5;
export const PAN_CLAMP = 4000;

interface WorkflowCanvasProps {
  nodes: WorkflowNodeData[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onDeleteNode: (nodeId: string) => void;
  onUpdateNodePosition: (nodeId: string, pos: { x: number; y: number }) => void;
  onAddEdge: (edge: WorkflowEdge) => void;
  onDeleteEdge: (edgeId: string) => void;
  viewport: Viewport;
  onViewportChange: (vp: Viewport) => void;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
}

export function WorkflowCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  onDeleteNode,
  onUpdateNodePosition,
  onAddEdge,
  onDeleteEdge,
  viewport,
  onViewportChange,
  isFullscreen,
  onToggleFullscreen,
}: WorkflowCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Connection drafting state
  const [connectingStart, setConnectingStart] = useState<{ nodeId: string; portId: string } | null>(null);
  const [dragLineEnd, setDragLineEnd] = useState<{ x: number; y: number } | null>(null);

  // Node drag state
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Pan state (Space+drag)
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [panOrigin, setPanOrigin] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [spaceDown, setSpaceDown] = useState(false);

  // Hovered edge for deletion
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);

  const { x: vx, y: vy, zoom } = viewport;

  // Convert graph coordinates to screen coordinates (apply viewport transform).
  const toScreen = useCallback(
    (gx: number, gy: number) => ({ x: gx * zoom + vx, y: gy * zoom + vy }),
    [zoom, vx, vy]
  );

  // Convert screen coordinates to graph coordinates (inverse viewport transform).
  const toGraph = useCallback(
    (sx: number, sy: number) => ({ x: (sx - vx) / zoom, y: (sy - vy) / zoom }),
    [zoom, vx, vy]
  );

  // Calculate absolute screen pixel coordinates for port handles.
  const getPortCoordinates = (nodeId: string, portId: string, portType: "input" | "output") => {
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return { x: 0, y: 0 };

    const CARD_WIDTH = 256; // 64 * 4px = 256px
    const HEADER_HEIGHT = 85;

    let gx = node.position.x;
    let gy = node.position.y + HEADER_HEIGHT;

    if (portType === "output") {
      gx += CARD_WIDTH;
    }

    return toScreen(gx, gy);
  };

  const handleMouseDownNode = (nodeId: string, e: React.MouseEvent) => {
    // Space+drag pans the canvas; do not start a node drag in that case.
    if (spaceDown) return;
    onSelectNode(nodeId);
    setDraggingNodeId(nodeId);
    const node = nodes.find((n) => n.id === nodeId);
    if (node) {
      const screen = toScreen(node.position.x, node.position.y);
      setDragOffset({
        x: e.clientX - screen.x,
        y: e.clientY - screen.y,
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning && containerRef.current) {
      const dx = e.clientX - panStart.x;
      const dy = e.clientY - panStart.y;
      onViewportChange({
        x: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, panOrigin.x + dx)),
        y: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, panOrigin.y + dy)),
        zoom,
      });
      return;
    }

    if (draggingNodeId && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      // Convert the screen-space drag delta back to graph coordinates using zoom.
      const graph = toGraph(e.clientX - rect.left - dragOffset.x, e.clientY - rect.top - dragOffset.y);
      const newX = Math.max(20, Math.min(2000, graph.x));
      const newY = Math.max(20, Math.min(2000, graph.y));
      onUpdateNodePosition(draggingNodeId, { x: newX, y: newY });
    }

    if (connectingStart && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDragLineEnd({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  };

  const handleMouseUp = () => {
    if (draggingNodeId) setDraggingNodeId(null);
    if (isPanning) setIsPanning(false);
    if (connectingStart) {
      setConnectingStart(null);
      setDragLineEnd(null);
    }
  };

  const handleStartConnection = (nodeId: string, portId: string, portType: "output", e: React.MouseEvent) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setConnectingStart({ nodeId, portId });
      setDragLineEnd({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  };

  const handleEndConnection = (targetNodeId: string, targetPortId: string, portType: "input") => {
    if (connectingStart && connectingStart.nodeId !== targetNodeId) {
      // Cycle detection check
      const createsCycle = (src: string, tgt: string): boolean => {
        if (src === tgt) return true;
        const outgoing = edges.filter((e) => e.source === tgt);
        for (const edge of outgoing) {
          if (createsCycle(src, edge.target)) return true;
        }
        return false;
      };

      if (createsCycle(connectingStart.nodeId, targetNodeId)) {
        alert("Cyclic flow detected! ContAIned DAG workflows require acyclic node topologies.");
      } else {
        const newEdge: WorkflowEdge = {
          id: `edge_${Date.now()}`,
          source: connectingStart.nodeId,
          sourceHandle: connectingStart.portId,
          target: targetNodeId,
          targetHandle: targetPortId,
        };
        onAddEdge(newEdge);
      }
    }
    setConnectingStart(null);
    setDragLineEnd(null);
  };

  // Zoom centered on the cursor position.
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const cursorX = e.clientX - rect.left;
    const cursorY = e.clientY - rect.top;

    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom * factor));
    if (newZoom === zoom) return;

    // Keep the point under the cursor fixed: adjust pan so the graph point
    // under the cursor stays at the same screen position.
    const graphX = (cursorX - vx) / zoom;
    const graphY = (cursorY - vy) / zoom;
    const newVx = cursorX - graphX * newZoom;
    const newVy = cursorY - graphY * newZoom;

    onViewportChange({
      x: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, newVx)),
      y: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, newVy)),
      zoom: newZoom,
    });
  };

  const handleBackgroundMouseDown = (e: React.MouseEvent) => {
    // Space+drag (or middle-mouse) pans the canvas background.
    if (spaceDown || e.button === 1) {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
      setPanOrigin({ x: vx, y: vy });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.code === "Space") {
      e.preventDefault();
      setSpaceDown(true);
    }
  };

  const handleKeyUp = (e: React.KeyboardEvent) => {
    if (e.code === "Space") {
      setSpaceDown(false);
    }
  };

  const zoomBy = (factor: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const cx = rect ? rect.width / 2 : 0;
    const cy = rect ? rect.height / 2 : 0;
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom * factor));
    if (newZoom === zoom) return;
    const graphX = (cx - vx) / zoom;
    const graphY = (cy - vy) / zoom;
    onViewportChange({
      x: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, cx - graphX * newZoom)),
      y: Math.max(-PAN_CLAMP, Math.min(PAN_CLAMP, cy - graphY * newZoom)),
      zoom: newZoom,
    });
  };

  const fitView = () => {
    if (nodes.length === 0) {
      onViewportChange({ x: 0, y: 0, zoom: 1 });
      return;
    }
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const minX = Math.min(...nodes.map((n) => n.position.x));
    const minY = Math.min(...nodes.map((n) => n.position.y));
    const maxX = Math.max(...nodes.map((n) => n.position.x + 256));
    const maxY = Math.max(...nodes.map((n) => n.position.y + 170));
    const pad = 60;
    const contentW = maxX - minX + pad * 2;
    const contentH = maxY - minY + pad * 2;
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.min(rect.width / contentW, rect.height / contentH)));
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    onViewportChange({
      x: rect.width / 2 - cx * newZoom,
      y: rect.height / 2 - cy * newZoom,
      zoom: newZoom,
    });
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseDown={handleBackgroundMouseDown}
      onWheel={handleWheel}
      onKeyDown={handleKeyDown}
      onKeyUp={handleKeyUp}
      onClick={() => onSelectNode(null)}
      tabIndex={0}
      className={`relative bg-slate-950/90 border border-slate-800 rounded-2xl overflow-hidden custom-scrollbar select-none ${
        isFullscreen
          ? "fixed inset-0 z-[100] w-screen h-screen rounded-none border-0"
          : "w-full h-[650px]"
      } ${spaceDown ? "cursor-grab" : "cursor-crosshair"}`}
      style={{
        backgroundImage: `radial-gradient(circle, #334155 1px, transparent 1px)`,
        backgroundSize: "24px 24px",
        backgroundPosition: `${vx}px ${vy}px`,
      }}
    >
      {/* Canvas Toolbar (zoom + fullscreen controls) */}
      <div className="absolute top-3 right-3 z-40 flex items-center space-x-1.5 bg-slate-900/90 border border-slate-800 rounded-xl p-1.5 shadow-lg">
        <button
          onClick={(e) => { e.stopPropagation(); zoomBy(1 / 1.1); }}
          className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-[10px] font-mono text-slate-400 px-1">{Math.round(zoom * 100)}%</span>
        <button
          onClick={(e) => { e.stopPropagation(); zoomBy(1.1); }}
          className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); fitView(); }}
          className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Fit view (0)"
        >
          <Focus className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-slate-700 mx-0.5" />
        <button
          onClick={(e) => { e.stopPropagation(); onToggleFullscreen(); }}
          className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title={isFullscreen ? "Exit fullscreen (Esc)" : "Enter fullscreen"}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* SVG Edge Connection Layer (screen space) */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-20 overflow-visible">
        <defs>
          <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#818cf8" />
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Existing Edges */}
        {edges.map((edge) => {
          const srcPos = getPortCoordinates(edge.source, edge.sourceHandle, "output");
          const tgtPos = getPortCoordinates(edge.target, edge.targetHandle, "input");

          const deltaX = Math.abs(tgtPos.x - srcPos.x) * 0.5;
          const pathD = `M ${srcPos.x} ${srcPos.y} C ${srcPos.x + deltaX} ${srcPos.y}, ${tgtPos.x - deltaX} ${tgtPos.y}, ${tgtPos.x} ${tgtPos.y}`;

          const isHovered = hoveredEdgeId === edge.id;

          return (
            <g key={edge.id} className="pointer-events-auto group">
              <path
                d={pathD}
                fill="none"
                stroke={isHovered ? "#f43f5e" : "url(#edge-gradient)"}
                strokeWidth={isHovered ? "3.5" : "2.5"}
                className="transition-all duration-150"
                filter={isHovered ? "url(#glow)" : undefined}
              />

              {/* Hit target for hovering/deleting edge */}
              <path
                d={pathD}
                fill="none"
                stroke="transparent"
                strokeWidth="16"
                onMouseEnter={() => setHoveredEdgeId(edge.id)}
                onMouseLeave={() => setHoveredEdgeId(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteEdge(edge.id);
                }}
                className="cursor-pointer"
              />

              {/* Delete Edge Badge on hover */}
              {isHovered && (
                <foreignObject
                  x={(srcPos.x + tgtPos.x) / 2 - 12}
                  y={(srcPos.y + tgtPos.y) / 2 - 12}
                  width="24"
                  height="24"
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteEdge(edge.id);
                    }}
                    className="w-6 h-6 rounded-full bg-rose-600 text-white flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
                    title="Delete connection edge"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </foreignObject>
              )}
            </g>
          );
        })}

        {/* Draft Connection Line being dragged */}
        {connectingStart && dragLineEnd && (
          <g>
            {(() => {
              const srcPos = getPortCoordinates(connectingStart.nodeId, connectingStart.portId, "output");
              const deltaX = Math.abs(dragLineEnd.x - srcPos.x) * 0.5;
              const draftD = `M ${srcPos.x} ${srcPos.y} C ${srcPos.x + deltaX} ${srcPos.y}, ${dragLineEnd.x - deltaX} ${dragLineEnd.y}, ${dragLineEnd.x} ${dragLineEnd.y}`;

              return (
                <path
                  d={draftD}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                  className="animate-pulse"
                />
              );
            })()}
          </g>
        )}
      </svg>

      {/* Node Layer (graph coordinates, transformed by viewport) */}
      <div
        className="absolute top-0 left-0 z-30 origin-top-left"
        style={{ transform: `translate(${vx}px, ${vy}px) scale(${zoom})` }}
      >
        {nodes.map((node) => (
          <div
            key={node.id}
            onMouseDown={(e) => handleMouseDownNode(node.id, e)}
            className="relative"
          >
            <WorkflowNodeCard
              node={node}
              isSelected={selectedNodeId === node.id}
              onSelect={onSelectNode}
              onDelete={onDeleteNode}
              onStartConnection={handleStartConnection}
              onEndConnection={handleEndConnection}
              isConnecting={!!connectingStart}
            />
          </div>
        ))}
      </div>

      {/* Empty State Banner */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center p-8 pointer-events-none">
          <div className="text-center space-y-3 bg-slate-900/80 border border-slate-800 p-8 rounded-2xl max-w-sm backdrop-blur-md">
            <AlertTriangle className="w-8 h-8 text-indigo-400 mx-auto animate-bounce" />
            <h3 className="text-sm font-bold text-slate-200">Execution Canvas Empty</h3>
            <p className="text-xs text-slate-400">
              Click nodes from the palette on the left to add them to your canvas. Drag handles to connect execution flows.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
