import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  GitFork,
  ArrowLeft,
  Save,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Play,
  Layers,
  Plus,
  Trash2,
  Loader2,
  Sparkles,
  Bot,
  Database,
  Award,
  Wrench,
  Split,
  FileCode,
  Globe,
  Flag,
  Zap,
  Copy,
  Undo2,
  Redo2,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";
import { WorkflowCanvas } from "./WorkflowCanvas";
import type { WorkflowEdge, Viewport } from "./WorkflowCanvas";
import { MIN_ZOOM, MAX_ZOOM } from "./WorkflowCanvas";
import { NODE_CONFIGS, getDefaultPortsForType } from "./WorkflowNodeCard";
import type { WorkflowNodeData } from "./WorkflowNodeCard";
import { WorkflowRunModal } from "./WorkflowRunModal";

interface ResourceSelectProps {
  loading: boolean;
  error: string | null;
  emptyMessage: string;
  loadingLabel: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  onRetry: () => void;
  accent?: string;
}

/**
 * Renders a property-drawer resource dropdown with explicit loading / empty /
 * error states so a user never sees a bare empty <select> and wonders whether
 * it is loading, failed, or genuinely empty.
 */
function ResourceSelect({
  loading,
  error,
  emptyMessage,
  loadingLabel,
  value,
  onChange,
  options,
  placeholder,
  onRetry,
  accent = "indigo",
}: ResourceSelectProps) {
  if (loading) {
    return (
      <div className="flex items-center space-x-2 text-xs text-slate-400 py-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        <span>{loadingLabel}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-400">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="px-2.5 py-1 text-[11px] font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (options.length === 0) {
    return <p className="text-xs text-slate-500 italic py-1">{emptyMessage}</p>;
  }

  const focusClass =
    accent === "cyan"
      ? "focus:border-cyan-500"
      : accent === "purple"
      ? "focus:border-purple-500"
      : accent === "emerald"
      ? "focus:border-emerald-500"
      : "focus:border-indigo-500";

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono focus:outline-none ${focusClass} text-xs`}
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

export function WorkflowEditor() {
  const { hubId, workflowId } = useParams<{ hubId: string; workflowId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { can, isArchived } = useHubPermissions();

  const [workflow, setWorkflow] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nodes, setNodes] = useState<WorkflowNodeData[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "dirty" | "saving">("saved");

  // Live Hub resources state for property drawer dropdowns
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [availableCollections, setAvailableCollections] = useState<any[]>([]);
  const [availableEvalSuites, setAvailableEvalSuites] = useState<any[]>([]);
  const [availableCredentials, setAvailableCredentials] = useState<any[]>([]);

  // Per-resource loading / error state for the property drawer dropdowns
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [evalSuitesLoading, setEvalSuitesLoading] = useState(false);
  const [credentialsLoading, setCredentialsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [evalSuitesError, setEvalSuitesError] = useState<string | null>(null);
  const [credentialsError, setCredentialsError] = useState<string | null>(null);

  // Test run modal
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);

  // Validate state
  const [isValidating, setIsValidating] = useState(false);
  const [validationIssues, setValidationIssues] = useState<any[]>([]);
  const [showIssuesPanel, setShowIssuesPanel] = useState(false);

  // Canvas viewport (pan/zoom) — controlled here so keyboard shortcuts can adjust it.
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });

  // Fullscreen canvas state (CSS fixed-overlay approach).
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Undo/redo history stack (capped at 50 entries).
  const historyRef = useRef<{ nodes: WorkflowNodeData[]; edges: WorkflowEdge[] }[]>([]);
  const historyIndexRef = useRef(-1);
  const HISTORY_CAP = 50;

  // Push a snapshot onto the undo history on every user-driven change.
  const pushHistory = useCallback((nextNodes: WorkflowNodeData[], nextEdges: WorkflowEdge[]) => {
    const history = historyRef.current;
    // Drop any redo branch ahead of the current index.
    const trimmed = history.slice(0, historyIndexRef.current + 1);
    trimmed.push({ nodes: nextNodes, edges: nextEdges });
    // Cap the stack.
    if (trimmed.length > HISTORY_CAP) trimmed.shift();
    historyRef.current = trimmed;
    historyIndexRef.current = trimmed.length - 1;
  }, []);

  const undo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    const snapshot = historyRef.current[historyIndexRef.current];
    if (snapshot) {
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      setIsDirty(true);
      setSaveStatus("dirty");
    }
  }, []);

  const redo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    historyIndexRef.current += 1;
    const snapshot = historyRef.current[historyIndexRef.current];
    if (snapshot) {
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      setIsDirty(true);
      setSaveStatus("dirty");
    }
  }, []);

  // Draft persistence key (frontend-only drafts per workflow)
  const draftKey = workflowId ? `contained_workflow_draft_${workflowId}` : null;

  // Load a starter graph passed via navigation state (from CreateWorkflowDialog template)
  const starterGraph = (location.state as any)?.starterGraph;

  const fetchWorkflowAndHubResources = async () => {
    if (!hubId || !workflowId) return;
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Workflow
      const data = await api.workflows.get(hubId, workflowId);

      // 2. Resolve the graph: prefer a frontend draft (localStorage), then the
      //    backend draft graph, then an empty graph.
      let graph: { nodes: any[]; edges: any[] } = { nodes: [], edges: [] };
      const localDraft = draftKey ? localStorage.getItem(draftKey) : null;
      if (localDraft) {
        try {
          const parsed = JSON.parse(localDraft);
          if (parsed && Array.isArray(parsed.nodes)) graph = parsed;
        } catch (e) {
          // ignore corrupt local draft
        }
      } else if (starterGraph && Array.isArray(starterGraph.nodes)) {
        graph = starterGraph;
      } else {
        const draftGraph = (data as any).draft_graph;
        if (draftGraph && Array.isArray(draftGraph.nodes)) {
          graph = { nodes: draftGraph.nodes, edges: draftGraph.edges || [] };
        }
      }

      setWorkflow(data);
      setNodes(graph.nodes || []);
      setEdges(graph.edges || []);

      // 3. Fetch active Hub resources for live select dropdowns.
      //    Agents come from linked agent hubs; collections from linked ingestion hubs.
      await fetchLinkedHubResources();

      setIsDirty(false);
      setSaveStatus("saved");
    } catch (err: any) {
      setError(err?.message || "Failed to load workflow canvas details");
    } finally {
      setLoading(false);
    }
  };

  // Fetch agents / collections / eval suites / credentials from linked hubs.
  // Each resource type is fetched independently so a failure in one does not
  // block the others, and each exposes its own loading / error state.
  const fetchLinkedHubResources = async (only?: "agents" | "collections" | "evalSuites" | "credentials") => {
    if (!hubId) return;

    // Discover outgoing hub links to know which hubs we may consume from.
    let links: any[] = [];
    try {
      links = (await api.hubs.links.list(hubId)) || [];
    } catch (e) {
      // ignore link fetch errors
    }

    // Always include the current hub's own resources too (same-hub fast path).
    const hubIds = new Set<string>([hubId]);
    for (const l of links) {
      if (l?.target_hub_id) hubIds.add(l.target_hub_id);
    }

    const fetchAgents = async () => {
      setAgentsLoading(true);
      setAgentsError(null);
      const agents: any[] = [];
      try {
        for (const hid of hubIds) {
          try {
            const res = await api.agents.list(hid);
            if (Array.isArray(res)) agents.push(...res);
          } catch (e) {}
        }
        // Deduplicate by id
        const seen = new Set<string>();
        const deduped = agents.filter((a) => {
          if (seen.has(a.id)) return false;
          seen.add(a.id);
          return true;
        });
        setAvailableAgents(deduped);
      } catch (err: any) {
        setAgentsError(err?.message || "Failed to load agents");
      } finally {
        setAgentsLoading(false);
      }
    };

    const fetchCollections = async () => {
      setCollectionsLoading(true);
      setCollectionsError(null);
      const collections: any[] = [];
      try {
        for (const hid of hubIds) {
          try {
            const res = await api.ingestion.collections.list(hid);
            const cols = res?.collections || [];
            if (Array.isArray(cols)) collections.push(...cols);
          } catch (e) {}
        }
        const seen = new Set<string>();
        const deduped = collections.filter((c) => {
          if (seen.has(c.id)) return false;
          seen.add(c.id);
          return true;
        });
        setAvailableCollections(deduped);
      } catch (err: any) {
        setCollectionsError(err?.message || "Failed to load collections");
      } finally {
        setCollectionsLoading(false);
      }
    };

    const fetchEvalSuites = async () => {
      setEvalSuitesLoading(true);
      setEvalSuitesError(null);
      const evalSuites: any[] = [];
      try {
        for (const hid of hubIds) {
          try {
            const res = await api.evals.suites.list(hid);
            if (Array.isArray(res)) evalSuites.push(...res);
          } catch (e) {}
        }
        const seen = new Set<string>();
        const deduped = evalSuites.filter((s) => {
          if (seen.has(s.id)) return false;
          seen.add(s.id);
          return true;
        });
        setAvailableEvalSuites(deduped);
      } catch (err: any) {
        setEvalSuitesError(err?.message || "Failed to load eval suites");
      } finally {
        setEvalSuitesLoading(false);
      }
    };

    const fetchCredentials = async () => {
      setCredentialsLoading(true);
      setCredentialsError(null);
      const credentials: any[] = [];
      try {
        for (const hid of hubIds) {
          try {
            const res = await api.dbCredentials.list(hid);
            if (Array.isArray(res)) credentials.push(...res);
          } catch (e) {}
        }
        const seen = new Set<string>();
        const deduped = credentials.filter((c) => {
          if (seen.has(c.id)) return false;
          seen.add(c.id);
          return true;
        });
        setAvailableCredentials(deduped);
      } catch (err: any) {
        setCredentialsError(err?.message || "Failed to load DB credentials");
      } finally {
        setCredentialsLoading(false);
      }
    };

    if (only === "agents") return fetchAgents();
    if (only === "collections") return fetchCollections();
    if (only === "evalSuites") return fetchEvalSuites();
    if (only === "credentials") return fetchCredentials();

    // Fetch all in parallel
    await Promise.all([fetchAgents(), fetchCollections(), fetchEvalSuites(), fetchCredentials()]);
  };

  useEffect(() => {
    fetchWorkflowAndHubResources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, workflowId]);

  // Persist the graph to localStorage whenever it changes (frontend-only draft).
  useEffect(() => {
    if (!draftKey) return;
    if (loading) return;
    try {
      localStorage.setItem(draftKey, JSON.stringify({ nodes, edges }));
    } catch (e) {
      // ignore quota / serialization errors
    }
  }, [nodes, edges, draftKey, loading]);

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  // Keyboard shortcuts scoped to the editor workspace
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inInput =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement;

      // Escape exits fullscreen
      if (e.key === "Escape" && isFullscreen && !inInput) {
        setIsFullscreen(false);
        return;
      }
      if (inInput) return;

      // Ctrl/Cmd + S -> Save Draft
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (isDirty && can("edit_resource") && !isArchived) {
          handleSaveDraft();
        }
        return;
      }
      // Ctrl/Cmd + Shift + Z -> Redo
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        redo();
        return;
      }
      // Ctrl/Cmd + Z -> Undo
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undo();
        return;
      }
      // Delete / Backspace -> Delete selected node
      if ((e.key === "Delete" || e.key === "Backspace") && selectedNodeId) {
        handleDeleteNode(selectedNodeId);
        return;
      }
      // Ctrl/Cmd + D -> Duplicate selected node
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d" && selectedNodeId) {
        e.preventDefault();
        const node = nodes.find((n) => n.id === selectedNodeId);
        if (node) {
          const dupNode: WorkflowNodeData = {
            ...node,
            id: `node_${Date.now()}`,
            label: `${node.label} (Copy)`,
            position: { x: node.position.x + 30, y: node.position.y + 30 },
          };
          const nextNodes = [...nodes, dupNode];
          setNodes(nextNodes);
          setSelectedNodeId(dupNode.id);
          setIsDirty(true);
          setSaveStatus("dirty");
          pushHistory(nextNodes, edges);
        }
        return;
      }
      // Zoom shortcuts
      if (e.key === "+" || e.key === "=") {
        setViewport((vp) => ({ ...vp, zoom: Math.min(MAX_ZOOM, +(vp.zoom * 1.1).toFixed(2)) }));
      }
      if (e.key === "-") {
        setViewport((vp) => ({ ...vp, zoom: Math.max(MIN_ZOOM, +(vp.zoom / 1.1).toFixed(2)) }));
      }
      if (e.key === "0") {
        setViewport({ x: 0, y: 0, zoom: 1 });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isFullscreen,
    isDirty,
    selectedNodeId,
    nodes,
    edges,
    can,
    isArchived,
    undo,
    redo,
    pushHistory,
  ]);

  // Auto-bind default available linked hub resources to unlinked nodes
  useEffect(() => {
    if (nodes.length === 0) return;
    let modified = false;
    const updatedNodes = nodes.map((node) => {
      const newData = { ...node.data };
      let nodeChanged = false;
      if (node.type === "agent" && !newData.agent_id && availableAgents.length > 0) {
        newData.agent_id = availableAgents[0].id;
        newData.agent_name = availableAgents[0].name || availableAgents[0].id;
        newData.hub_id = hubId;
        nodeChanged = true;
      }
      if (node.type === "retrieval" && !newData.collection_id && availableCollections.length > 0) {
        newData.collection_id = availableCollections[0].id;
        newData.collection_name = availableCollections[0].name || availableCollections[0].id;
        newData.hub_id = hubId;
        nodeChanged = true;
      }
      if (node.type === "eval" && !newData.suite_id && availableEvalSuites.length > 0) {
        newData.suite_id = availableEvalSuites[0].id;
        newData.suite_name = availableEvalSuites[0].name || availableEvalSuites[0].id;
        newData.hub_id = hubId;
        nodeChanged = true;
      }
      if ((node.type === "db_store" || node.type === "database_query") && !newData.credential_id && availableCredentials.length > 0) {
        newData.credential_id = availableCredentials[0].id;
        newData.credential_name = availableCredentials[0].name || availableCredentials[0].id;
        newData.hub_id = hubId;
        nodeChanged = true;
      }
      if (nodeChanged) {
        modified = true;
        return { ...node, data: newData };
      }
      return node;
    });

    if (modified) {
      setNodes(updatedNodes);
    }
  }, [availableAgents, availableCollections, availableEvalSuites, availableCredentials, hubId]);

  const handleAddNode = (type: string, overridePos?: { x: number; y: number }) => {
    const config = NODE_CONFIGS[type] || { label: type.toUpperCase() };
    const newNodeCount = nodes.length + 1;

    // Find a free grid slot that does not overlap any existing node.
    const CARD_W = 280;
    const CARD_H = 170;
    const occupied = nodes.map((n) => n.position);
    let pos = overridePos || { x: 80, y: 80 };
    if (!overridePos) {
      let col = 0;
      let row = 0;
      let found = false;
      while (!found && row < 20) {
        const candidate = { x: 80 + col * CARD_W, y: 80 + row * CARD_H };
        const overlaps = occupied.some(
          (p) => Math.abs(p.x - candidate.x) < CARD_W && Math.abs(p.y - candidate.y) < CARD_H
        );
        if (!overlaps) {
          pos = candidate;
          found = true;
        } else {
          col += 1;
          if (col >= 3) {
            col = 0;
            row += 1;
          }
        }
      }
    }

    const initialData: Record<string, any> = {};
    if (type === "agent" && availableAgents.length > 0) {
      initialData.agent_id = availableAgents[0].id;
      initialData.agent_name = availableAgents[0].name || availableAgents[0].id;
      initialData.hub_id = hubId;
    } else if (type === "retrieval" && availableCollections.length > 0) {
      initialData.collection_id = availableCollections[0].id;
      initialData.collection_name = availableCollections[0].name || availableCollections[0].id;
      initialData.hub_id = hubId;
    } else if (type === "eval" && availableEvalSuites.length > 0) {
      initialData.suite_id = availableEvalSuites[0].id;
      initialData.suite_name = availableEvalSuites[0].name || availableEvalSuites[0].id;
      initialData.hub_id = hubId;
    } else if ((type === "db_store" || type === "database_query") && availableCredentials.length > 0) {
      initialData.credential_id = availableCredentials[0].id;
      initialData.credential_name = availableCredentials[0].name || availableCredentials[0].id;
      initialData.hub_id = hubId;
    }

    const newNode: WorkflowNodeData = {
      id: `node_${Date.now()}`,
      type,
      label: `${config.label} ${newNodeCount}`,
      data: initialData,
      position: pos,
      ports: getDefaultPortsForType(type, {}),
    };

    const nextNodes = [...nodes, newNode];
    setNodes(nextNodes);
    setSelectedNodeId(newNode.id);
    setIsDirty(true);
    setSaveStatus("dirty");
    pushHistory(nextNodes, edges);
  };

  const handleDeleteNode = (nodeId: string) => {
    const nextNodes = nodes.filter((n) => n.id !== nodeId);
    const nextEdges = edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
    setNodes(nextNodes);
    setEdges(nextEdges);
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
    setIsDirty(true);
    setSaveStatus("dirty");
    pushHistory(nextNodes, nextEdges);
  };

  const handleUpdateNodePosition = (nodeId: string, pos: { x: number; y: number }) => {
    setNodes((prev) => prev.map((n) => (n.id === nodeId ? { ...n, position: pos } : n)));
    setIsDirty(true);
    setSaveStatus("dirty");
  };

  const handleAddEdge = (newEdge: WorkflowEdge) => {
    // Avoid duplicates
    if (edges.some((e) => e.source === newEdge.source && e.target === newEdge.target && e.sourceHandle === newEdge.sourceHandle)) {
      return;
    }
    const nextEdges = [...edges, newEdge];
    setEdges(nextEdges);
    setIsDirty(true);
    setSaveStatus("dirty");
    pushHistory(nodes, nextEdges);
  };

  const handleDeleteEdge = (edgeId: string) => {
    const nextEdges = edges.filter((e) => e.id !== edgeId);
    setEdges(nextEdges);
    setIsDirty(true);
    setSaveStatus("dirty");
    pushHistory(nodes, nextEdges);
  };

  const handleSaveDraft = async () => {
    if (!hubId || !workflowId) return;
    setIsSaving(true);
    setSaveStatus("saving");
    try {
      // Persist the graph to the backend draft endpoint (PUT /{wf_id}/draft).
      await api.workflows.updateDraft(hubId, workflowId, { nodes, edges });
      // Clear the frontend-only draft now that it is persisted server-side.
      if (draftKey) {
        try {
          localStorage.removeItem(draftKey);
        } catch (e) {}
      }
      setIsDirty(false);
      setSaveStatus("saved");
    } catch (err: any) {
      console.error("Failed to save draft workflow:", err);
      setSaveStatus("dirty");
    } finally {
      setIsSaving(false);
    }
  };

  const handleValidate = async () => {
    if (!hubId || !workflowId) return;
    setIsValidating(true);
    setValidationIssues([]);
    try {
      const result = await api.workflows.validate(hubId, workflowId, { nodes, edges });
      const allIssues = [...(result.errors || []), ...(result.warnings || [])];
      setValidationIssues(allIssues);
      setShowIssuesPanel(true);
    } catch (err: any) {
      console.error("Validation call failed:", err);
      setValidationIssues([{ code: "VALIDATE_ERROR", level: "error", message: err?.message || "Validation failed" }]);
      setShowIssuesPanel(true);
    } finally {
      setIsValidating(false);
    }
  };

  /** Node IDs that have at least one validation error/warning */
  const invalidNodeIds = new Set<string>(validationIssues.map((i: any) => i.node_id).filter(Boolean));

  // Validation summary
  const validationStatus = useMemo(() => {
    if (nodes.length === 0) return { ok: true, msg: "Canvas empty" };

    const unlinkedNodes = nodes.filter((n) => {
      if (n.type === "agent" && !n.data?.agent_id) return true;
      if (n.type === "retrieval" && !n.data?.collection_id) return true;
      if (n.type === "eval" && !n.data?.suite_id) return true;
      return false;
    });

    if (unlinkedNodes.length > 0) {
      return { ok: false, msg: `${unlinkedNodes.length} node(s) missing Hub resource link` };
    }

    return { ok: true, msg: "DAG Topology Valid" };
  }, [nodes]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm font-mono text-slate-400">Loading Workflow visual flow editor...</p>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200">Workflow Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not load target workflow canvas"}</p>
        <button
          onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-lg hover:bg-slate-700"
        >
          Back to Workflow Library
        </button>
      </div>
    );
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const editorContent = (
    <div
      className={
        isFullscreen
          ? "fixed inset-0 z-[9999] bg-[#090d16] p-6 overflow-hidden flex flex-col h-screen w-screen space-y-4"
          : "space-y-6 pb-12"
      }
    >
      {/* Editor Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4 shrink-0">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Workflow Library"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-xl font-bold font-display text-slate-100">{workflow.name}</h1>
              <span className={`px-2.5 py-0.5 text-xs font-mono font-semibold uppercase rounded-full border ${
                saveStatus === "saved"
                  ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/40"
                  : saveStatus === "saving"
                  ? "bg-indigo-950/60 text-indigo-400 border-indigo-800/40"
                  : "bg-amber-950/60 text-amber-400 border-amber-800/40"
              }`}>
                {saveStatus === "saved" ? "Saved • v1 Draft" : saveStatus === "saving" ? "Saving..." : "Unsaved Changes"}
              </span>

              {/* Validation Status Badge */}
              <span className={`px-2.5 py-0.5 text-xs font-mono font-semibold rounded-full border flex items-center space-x-1 ${
                validationStatus.ok
                  ? "bg-indigo-950/60 text-indigo-300 border-indigo-800/40"
                  : "bg-amber-950/60 text-amber-400 border-amber-800/40"
              }`}>
                {validationStatus.ok ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                <span>{validationStatus.msg}</span>
              </span>
            </div>
            <p className="text-xs font-mono text-slate-500 mt-1">
              {nodes.length} nodes, {edges.length} flow connections
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleValidate}
            disabled={isValidating || nodes.length === 0}
            title="Validate graph topology and cross-hub references"
            className="flex items-center space-x-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 font-medium text-xs rounded-xl border border-slate-700 transition-colors"
          >
            {isValidating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />}
            <span>Validate</span>
          </button>

          <button
            onClick={() => setIsRunModalOpen(true)}
            className="flex items-center space-x-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs rounded-xl border border-slate-700 transition-colors"
          >
            <Play className="w-3.5 h-3.5 text-emerald-400 fill-current" />
            <span>Run Test</span>
          </button>

          <button
            onClick={handleToggleFullscreen}
            title={isFullscreen ? "Exit Fullscreen Workspace (Esc)" : "Fullscreen Workspace"}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs rounded-xl border border-slate-700 transition-colors"
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5 text-indigo-400" /> : <Maximize2 className="w-3.5 h-3.5 text-indigo-400" />}
            <span>{isFullscreen ? "Exit Fullscreen" : "Fullscreen"}</span>
          </button>

          {isDirty && can("edit_resource") && !isArchived && (
            <button
              onClick={handleSaveDraft}
              disabled={isSaving}
              className="flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg transition-colors"
            >
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>Save Draft</span>
            </button>
          )}
        </div>
      </div>

      {/* Validation Issues Panel */}
      {showIssuesPanel && (
        <div className={`rounded-xl border p-4 shrink-0 ${
          validationIssues.length === 0
            ? "bg-emerald-950/20 border-emerald-800/40"
            : "bg-amber-950/20 border-amber-800/40"
        }`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              {validationIssues.length === 0
                ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                : <AlertTriangle className="w-4 h-4 text-amber-400" />}
              <span className="text-xs font-semibold font-mono text-slate-300">
                {validationIssues.length === 0
                  ? "Graph Valid — No issues detected"
                  : `${validationIssues.length} validation issue(s) found`}
              </span>
            </div>
            <button
              onClick={() => setShowIssuesPanel(false)}
              className="text-slate-500 hover:text-slate-300 text-xs font-mono transition-colors"
            >
              Dismiss
            </button>
          </div>
          {validationIssues.length > 0 && (
            <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar">
              {validationIssues.map((issue: any, idx: number) => (
                <div
                  key={idx}
                  className={`flex items-start space-x-2 text-xs font-mono px-3 py-1.5 rounded-lg ${
                    issue.level === "error"
                      ? "bg-red-950/40 text-red-300 border border-red-800/30"
                      : "bg-amber-950/40 text-amber-300 border border-amber-800/30"
                  }`}
                >
                  <span className="shrink-0 font-bold text-[10px] uppercase tracking-wide">{issue.code}</span>
                  {issue.node_id && (
                    <span className="text-slate-500 shrink-0">node: {issue.node_id}</span>
                  )}
                  <span className="text-slate-400 flex-1">{issue.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Workspace Layout (Palette | Canvas | Properties Drawer) */}
      <div className={`grid grid-cols-1 lg:grid-cols-12 gap-6 ${isFullscreen ? "flex-1 min-h-0" : "min-h-[650px]"}`}>
        {/* Left Column: Categorized Node Palette (3 Cols) */}
        <div className={`lg:col-span-3 bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4 space-y-4 flex flex-col justify-between custom-scrollbar overflow-y-auto ${isFullscreen ? "h-full max-h-none" : "max-h-[650px]"}`}>
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase font-mono text-slate-400">Node Palette</h3>

            {/* Triggers */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-mono text-slate-500 uppercase">Triggers & Inputs</span>
              <button
                onClick={() => handleAddNode("start")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Play className="w-4 h-4 text-emerald-400" />
                <span>Workflow Input</span>
              </button>
              <button
                onClick={() => handleAddNode("webhook")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Globe className="w-4 h-4 text-emerald-400" />
                <span>HTTP Webhook</span>
              </button>
            </div>

            {/* Hub Integrations */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-mono text-slate-500 uppercase">Hub Integrations</span>
              <button
                onClick={() => handleAddNode("agent")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Bot className="w-4 h-4 text-indigo-400" />
                <span>Agent Invocation</span>
              </button>

              <button
                onClick={() => handleAddNode("retrieval")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Database className="w-4 h-4 text-cyan-400" />
                <span>Vector Retrieval</span>
              </button>

              <button
                onClick={() => handleAddNode("eval")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Award className="w-4 h-4 text-purple-400" />
                <span>Eval Suite Run</span>
              </button>

              <button
                onClick={() => handleAddNode("mcp_tool")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Wrench className="w-4 h-4 text-amber-400" />
                <span>MCP Tool Execution</span>
              </button>

              <button
                onClick={() => handleAddNode("database_query")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Database className="w-4 h-4 text-emerald-400" />
                <span>Database Query</span>
              </button>

              <button
                onClick={() => handleAddNode("db_store")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Database className="w-4 h-4 text-emerald-400" />
                <span>DB Store</span>
              </button>
            </div>

            {/* Logic & Control */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-mono text-slate-500 uppercase">Logic & Control</span>
              <button
                onClick={() => handleAddNode("if_else")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Split className="w-4 h-4 text-amber-400" />
                <span>If / Else Condition</span>
              </button>

              <button
                onClick={() => handleAddNode("router")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <GitFork className="w-4 h-4 text-amber-400" />
                <span>Intent Router</span>
              </button>
            </div>

            {/* Transform & Output */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-mono text-slate-500 uppercase">Transform & Output</span>
              <button
                onClick={() => handleAddNode("transform")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Sparkles className="w-4 h-4 text-sky-400" />
                <span>Transform JSON</span>
              </button>

              <button
                onClick={() => handleAddNode("coding")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <FileCode className="w-4 h-4 text-sky-400" />
                <span>Code Script</span>
              </button>

              <button
                onClick={() => handleAddNode("final_message")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2.5 transition-all"
              >
                <Flag className="w-4 h-4 text-rose-400" />
                <span>Final Output</span>
              </button>
            </div>
          </div>
        </div>

        {/* Center Column: Interactive Visual Canvas (6 Cols) */}
        <div className={`lg:col-span-6 flex flex-col ${isFullscreen ? "h-full" : ""}`}>
          <WorkflowCanvas
            nodes={nodes}
            edges={edges}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            onDeleteNode={handleDeleteNode}
            onUpdateNodePosition={handleUpdateNodePosition}
            onAddEdge={handleAddEdge}
            onDeleteEdge={handleDeleteEdge}
            viewport={viewport}
            onViewportChange={setViewport}
            isFullscreen={isFullscreen}
            onToggleFullscreen={handleToggleFullscreen}
          />
        </div>

        {/* Right Column: Node Properties Drawer (3 Cols) */}
        <div className={`lg:col-span-3 bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4 space-y-4 custom-scrollbar overflow-y-auto ${isFullscreen ? "h-full max-h-none" : "max-h-[650px]"}`}>
          <h3 className="text-xs font-bold uppercase font-mono text-slate-400">Node Configuration</h3>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              {/* Common Label */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">Node Title</label>
                <input
                  type="text"
                  value={selectedNode.label}
                  onChange={(e) => {
                    const newLabel = e.target.value;
                    setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, label: newLabel } : n)));
                    setIsDirty(true);
                    setSaveStatus("dirty");
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Agent Node Configuration */}
              {selectedNode.type === "agent" && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-indigo-400 mb-1">Select Agent Hub Agent</label>
                  <ResourceSelect
                    loading={agentsLoading}
                    error={agentsError}
                    emptyMessage="No linked agents available"
                    loadingLabel="Loading agents…"
                    value={selectedNode.data?.agent_id || ""}
                    onChange={(agentId) => {
                      const selectedAgent = availableAgents.find((a) => a.id === agentId);
                      setNodes(
                        nodes.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  agent_id: agentId,
                                  agent_name: selectedAgent?.name || agentId,
                                  hub_id: hubId,
                                },
                              }
                            : n
                        )
                      );
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    options={availableAgents.map((ag) => ({
                      value: ag.id,
                      label: `${ag.name} (${ag.model})`,
                    }))}
                    placeholder="-- Choose Provisioned Agent --"
                    onRetry={() => fetchLinkedHubResources("agents")}
                  />
                </div>
              )}

              {/* Retrieval Node Configuration */}
              {selectedNode.type === "retrieval" && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-cyan-400 mb-1">Select Ingestion Hub Collection</label>
                  <ResourceSelect
                    loading={collectionsLoading}
                    error={collectionsError}
                    emptyMessage="No linked collections available"
                    loadingLabel="Loading collections…"
                    value={selectedNode.data?.collection_id || ""}
                    onChange={(colId) => {
                      const selectedCol = availableCollections.find((c) => c.id === colId);
                      setNodes(
                        nodes.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  collection_id: colId,
                                  collection_name: selectedCol?.name || colId,
                                  hub_id: hubId,
                                },
                              }
                            : n
                        )
                      );
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    options={availableCollections.map((col) => ({
                      value: col.id,
                      label: `${col.name} (${col.chunk_count || 0} chunks)`,
                    }))}
                    placeholder="-- Choose Vector Collection --"
                    onRetry={() => fetchLinkedHubResources("collections")}
                    accent="cyan"
                  />

                  <div>
                    <label className="block text-[10px] font-mono text-slate-400 mb-1">Retrieval Strategy</label>
                    <select
                      value={selectedNode.data?.strategy || "hybrid"}
                      onChange={(e) => {
                        const strat = e.target.value;
                        setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, strategy: strat } } : n)));
                        setIsDirty(true);
                      }}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 font-mono text-xs"
                    >
                      <option value="vector">Dense Vector Search</option>
                      <option value="hybrid">Hybrid (BM25 + Vector + Graph)</option>
                      <option value="graph">Graph Traversal Only</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Eval Node Configuration */}
              {selectedNode.type === "eval" && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-purple-400 mb-1">Select Eval Hub Suite</label>
                  <ResourceSelect
                    loading={evalSuitesLoading}
                    error={evalSuitesError}
                    emptyMessage="No linked eval suites available"
                    loadingLabel="Loading eval suites…"
                    value={selectedNode.data?.suite_id || ""}
                    onChange={(suiteId) => {
                      const selectedSuite = availableEvalSuites.find((s) => s.id === suiteId);
                      setNodes(
                        nodes.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  suite_id: suiteId,
                                  suite_name: selectedSuite?.name || suiteId,
                                  hub_id: hubId,
                                },
                              }
                            : n
                        )
                      );
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    options={availableEvalSuites.map((suite) => ({
                      value: suite.id,
                      label: suite.name,
                    }))}
                    placeholder="-- Choose Eval Suite --"
                    onRetry={() => fetchLinkedHubResources("evalSuites")}
                    accent="purple"
                  />
                </div>
              )}

              {/* If/Else Condition Config */}
              {selectedNode.type === "if_else" && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-amber-400 mb-1">Condition Expression</label>
                  <input
                    type="text"
                    value={selectedNode.data?.condition || "score >= 0.7"}
                    onChange={(e) => {
                      const cond = e.target.value;
                      setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, condition: cond } } : n)));
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono focus:outline-none focus:border-amber-500 text-xs"
                  />
                </div>
              )}

              {/* Database Query Node Configuration */}
              {(selectedNode.type === "database_query" || selectedNode.type === "DatabaseQueryNode") && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-emerald-400 mb-1">Select Database Connection</label>
                  <ResourceSelect
                    loading={credentialsLoading}
                    error={credentialsError}
                    emptyMessage="No linked DB credentials available"
                    loadingLabel="Loading DB credentials…"
                    value={selectedNode.data?.credential_id || ""}
                    onChange={(credId) => {
                      const selectedCred = availableCredentials.find((c) => c.id === credId);
                      setNodes(
                        nodes.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  credential_id: credId,
                                  credential_name: selectedCred?.name || credId,
                                  hub_id: hubId,
                                },
                              }
                            : n
                        )
                      );
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    options={availableCredentials.map((cred) => ({
                      value: cred.id,
                      label: `${cred.name} (${cred.db_type})`,
                    }))}
                    placeholder="-- Choose Database Connection --"
                    onRetry={() => fetchLinkedHubResources("credentials")}
                    accent="emerald"
                  />

                  <div>
                    <label className="block text-[10px] font-mono text-slate-400 mb-1">Parametrized SQL Query</label>
                    <textarea
                      rows={4}
                      value={selectedNode.data?.query_template || ""}
                      onChange={(e) => {
                        const q = e.target.value;
                        setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, query_template: q } } : n)));
                        setIsDirty(true);
                        setSaveStatus("dirty");
                      }}
                      placeholder="SELECT * FROM users WHERE user_id = :user_id"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono focus:outline-none focus:border-emerald-500 text-xs resize-y"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-mono text-slate-400 mb-1">Timeout (s)</label>
                      <input
                        type="number"
                        min={1}
                        value={selectedNode.data?.timeout_s || 30}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, timeout_s: v } } : n)));
                          setIsDirty(true);
                        }}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono text-slate-400 mb-1">Max Rows</label>
                      <input
                        type="number"
                        min={1}
                        value={selectedNode.data?.max_rows || 500}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, max_rows: v } } : n)));
                          setIsDirty(true);
                        }}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 font-mono text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* DB Store Node Configuration */}
              {(selectedNode.type === "db_store" || selectedNode.type === "DBStoreNode") && (
                <div className="space-y-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <label className="block text-[11px] font-semibold text-emerald-400 mb-1">Select Database Connection</label>
                  <ResourceSelect
                    loading={credentialsLoading}
                    error={credentialsError}
                    emptyMessage="No linked DB credentials available"
                    loadingLabel="Loading DB credentials…"
                    value={selectedNode.data?.credential_id || ""}
                    onChange={(credId) => {
                      const selectedCred = availableCredentials.find((c) => c.id === credId);
                      setNodes(
                        nodes.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  credential_id: credId,
                                  credential_name: selectedCred?.name || credId,
                                  hub_id: hubId,
                                },
                              }
                            : n
                        )
                      );
                      setIsDirty(true);
                      setSaveStatus("dirty");
                    }}
                    options={availableCredentials.map((cred) => ({
                      value: cred.id,
                      label: `${cred.name} (${cred.db_type})`,
                    }))}
                    placeholder="-- Choose Database Connection --"
                    onRetry={() => fetchLinkedHubResources("credentials")}
                    accent="emerald"
                  />

                  <div>
                    <label className="block text-[10px] font-mono text-slate-400 mb-1">Target Table / Collection</label>
                    <input
                      type="text"
                      value={selectedNode.data?.target_table || ""}
                      onChange={(e) => {
                        const t = e.target.value;
                        setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, target_table: t } } : n)));
                        setIsDirty(true);
                        setSaveStatus("dirty");
                      }}
                      placeholder="users"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono focus:outline-none focus:border-emerald-500 text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-mono text-slate-400 mb-1">Operation</label>
                    <select
                      value={selectedNode.data?.operation || "insert"}
                      onChange={(e) => {
                        const op = e.target.value;
                        setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, operation: op } } : n)));
                        setIsDirty(true);
                      }}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 font-mono text-xs"
                    >
                      <option value="insert">Insert</option>
                      <option value="upsert">Upsert</option>
                      <option value="append">Append</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic p-4 text-center border border-dashed border-slate-800 rounded-xl">
              Select a node on the canvas surface to configure properties and link Hub resources.
            </p>
          )}
        </div>
      </div>

      {/* Test Run Execution Modal */}
      {hubId && workflowId && (
        <WorkflowRunModal
          isOpen={isRunModalOpen}
          onClose={() => setIsRunModalOpen(false)}
          hubId={hubId}
          workflowId={workflowId}
        />
      )}
    </div>
  );

  if (isFullscreen) {
    return createPortal(editorContent, document.body);
  }

  return editorContent;
}
