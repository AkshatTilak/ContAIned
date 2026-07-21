export interface WorkflowNode {
  id: string;
  type: string;
  data: Record<string, any>;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface Workflow {
  id: string;
  name: string;
  graph_json: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
  };
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowSlice {
  workflows: Workflow[];
  activeWorkflow: Workflow | null;
  selectedNodeId: string | null;
  drawerOpen: boolean;
  setWorkflows: (workflows: Workflow[]) => void;
  setActiveWorkflow: (workflow: Workflow | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
}

export const createWorkflowSlice = (set: any): WorkflowSlice => ({
  workflows: [],
  activeWorkflow: null,
  selectedNodeId: null,
  drawerOpen: false,
  setWorkflows: (workflows) => set(() => ({ workflows })),
  setActiveWorkflow: (activeWorkflow) => set(() => ({ activeWorkflow })),
  setSelectedNodeId: (selectedNodeId) =>
    set(() => ({ selectedNodeId, drawerOpen: selectedNodeId !== null })),
  setDrawerOpen: (drawerOpen) => set(() => ({ drawerOpen })),
});
