import { create } from 'zustand';
import { createMetricsSlice, type MetricsSlice } from './metricsSlice';
import { createAgentSlice, type AgentSlice } from './agentSlice';
import { createWorkflowSlice, type WorkflowSlice } from './workflowSlice';

export type StoreState = MetricsSlice & AgentSlice & WorkflowSlice;

export const useStore = create<StoreState>()((set) => ({
  ...createMetricsSlice(set),
  ...createAgentSlice(set),
  ...createWorkflowSlice(set),
}));

export type { Agent } from './agentSlice';
export type { WorkflowNode, WorkflowEdge, Workflow } from './workflowSlice';
