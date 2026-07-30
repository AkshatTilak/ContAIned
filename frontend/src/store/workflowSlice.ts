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
  slug?: string;
  description?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowSlice {
  workflows: Workflow[];
  selectedNodeId: string | null;
  drawerOpen: boolean;
  setWorkflows: (workflows: Workflow[]) => void;
  setSelectedNodeId: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
}

export const createWorkflowSlice = (set: any): WorkflowSlice => ({
  workflows: [],
  selectedNodeId: null,
  drawerOpen: false,
  setWorkflows: (workflows) => set(() => ({ workflows })),
  setSelectedNodeId: (selectedNodeId) =>
    set(() => ({ selectedNodeId, drawerOpen: selectedNodeId !== null })),
  setDrawerOpen: (drawerOpen) => set(() => ({ drawerOpen })),
});
