import { create } from 'zustand';
import { MetricsSlice, createMetricsSlice } from './metricsSlice';
import { AgentSlice, createAgentSlice } from './agentSlice';
import { WorkflowSlice, createWorkflowSlice } from './workflowSlice';

export type StoreState = MetricsSlice & AgentSlice & WorkflowSlice;

export const useStore = create<StoreState>()((...args) => ({
  ...createMetricsSlice(...args),
  ...createAgentSlice(...args),
  ...createWorkflowSlice(...args),
}));
