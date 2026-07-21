import type { StateCreator } from "zustand";

export interface SettingsState {
  gatewayUrl: string;
  apiKey: string;
  vramBudgetMb: number;
  sidebarCollapsed: boolean;
}

export interface SettingsActions {
  setGatewayUrl: (url: string) => void;
  setApiKey: (key: string) => void;
  setVramBudgetMb: (mb: number) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  updateSettings: (settings: Partial<SettingsState>) => void;
  resetSettings: () => void;
}

export type SettingsSlice = SettingsState & SettingsActions;

const STORAGE_KEY = "contained-settings";

export const DEFAULT_SETTINGS: SettingsState = {
  gatewayUrl: import.meta.env.VITE_API_URL || "http://localhost:8000",
  apiKey: "sk_live_default_key",
  vramBudgetMb: 8000,
  sidebarCollapsed: false,
};

const loadPersistedSettings = (): SettingsState => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch {
    // ignore parse error
  }
  return DEFAULT_SETTINGS;
};

const persistSettings = (state: SettingsState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore save error
  }
};

export const createSettingsSlice: StateCreator<SettingsSlice, [], [], SettingsSlice> = (set) => {
  const initial = loadPersistedSettings();

  return {
    ...initial,
    setGatewayUrl: (gatewayUrl) =>
      set((state) => {
        const next = { ...state, gatewayUrl };
        persistSettings(next);
        return next;
      }),
    setApiKey: (apiKey) =>
      set((state) => {
        const next = { ...state, apiKey };
        persistSettings(next);
        return next;
      }),
    setVramBudgetMb: (vramBudgetMb) =>
      set((state) => {
        const next = { ...state, vramBudgetMb };
        persistSettings(next);
        return next;
      }),
    setSidebarCollapsed: (sidebarCollapsed) =>
      set((state) => {
        const next = { ...state, sidebarCollapsed };
        persistSettings(next);
        return next;
      }),
    updateSettings: (partial) =>
      set((state) => {
        const next = { ...state, ...partial };
        persistSettings(next);
        return next;
      }),
    resetSettings: () => {
      persistSettings(DEFAULT_SETTINGS);
      return set(DEFAULT_SETTINGS);
    },
  };
};
