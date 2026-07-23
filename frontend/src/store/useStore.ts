import { create } from 'zustand';
import { createMetricsSlice, type MetricsSlice } from './metricsSlice';
import { createAgentSlice, type AgentSlice } from './agentSlice';
import { createWorkflowSlice, type WorkflowSlice } from './workflowSlice';
import { createSettingsSlice, type SettingsSlice } from './settingsSlice';
import { createNotificationSlice, type NotificationSlice } from './notificationSlice';
import { createIngestionSlice, type IngestionSlice } from './ingestionSlice';
import { createAuthSlice, type AuthSlice, type UserProfile } from './authSlice';

export type StoreState = MetricsSlice & AgentSlice & WorkflowSlice & SettingsSlice & NotificationSlice & IngestionSlice & AuthSlice;

export const useStore = create<StoreState>()((set, get, api) => ({
  ...createMetricsSlice(set),
  ...createAgentSlice(set),
  ...createWorkflowSlice(set),
  ...createSettingsSlice(set, get, api),
  ...createNotificationSlice(set, get, api),
  ...createIngestionSlice(set, get, api),
  ...createAuthSlice(set, get, api),
}));

export type { Agent } from './agentSlice';
export type { WorkflowNode, WorkflowEdge, Workflow } from './workflowSlice';
export type { SettingsState } from './settingsSlice';
export type { Notification } from './notificationSlice';
export type { UserProfile } from './authSlice';


