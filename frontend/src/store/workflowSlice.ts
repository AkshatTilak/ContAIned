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

export interface WorkflowSlice {
  selectedNodeId: string | null;
  drawerOpen: boolean;
  setSelectedNodeId: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
}

export const createWorkflowSlice = (set: any): WorkflowSlice => ({
  selectedNodeId: null,
  drawerOpen: false,
  setSelectedNodeId: (selectedNodeId) =>
    set(() => ({ selectedNodeId, drawerOpen: selectedNodeId !== null })),
  setDrawerOpen: (drawerOpen) => set(() => ({ drawerOpen })),
});
