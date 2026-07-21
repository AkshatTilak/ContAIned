export interface Agent {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model_id: string;
  tools: string[];
  temperature: number;
  max_tokens: number;
  created_at?: string;
  updated_at?: string;
}

export interface AgentSlice {
  agents: Agent[];
  selectedAgentId: string | null;
  setAgents: (agents: Agent[]) => void;
  addAgent: (agent: Agent) => void;
  updateAgentInStore: (id: string, agent: Partial<Agent>) => void;
  removeAgent: (id: string) => void;
  setSelectedAgentId: (id: string | null) => void;
}

export const createAgentSlice = (set: any): AgentSlice => ({
  agents: [],
  selectedAgentId: null,
  setAgents: (agents) => set(() => ({ agents })),
  addAgent: (agent) => set((state: any) => ({ agents: [...state.agents, agent] })),
  updateAgentInStore: (id, updated) =>
    set((state: any) => ({
      agents: state.agents.map((a: Agent) => (a.id === id ? { ...a, ...updated } : a)),
    })),
  removeAgent: (id) =>
    set((state: any) => ({
      agents: state.agents.filter((a: Agent) => a.id !== id),
      selectedAgentId: state.selectedAgentId === id ? null : state.selectedAgentId,
    })),
  setSelectedAgentId: (id) => set(() => ({ selectedAgentId: id })),
});
