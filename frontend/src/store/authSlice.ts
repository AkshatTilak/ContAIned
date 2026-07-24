import type { StateCreator } from "zustand";
import type { StoreState } from "./useStore";
import { api } from "../services/api";

export interface UserProfile {
  id: string;
  email: string;
  display_name?: string;
  avatar_url?: string;
  provider: string;
  role: string;
  is_active: boolean;
}

export interface AuthSlice {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isAuthEnabled: boolean;
  authLoading: boolean;
  setUser: (user: UserProfile | null) => void;
  setToken: (token: string | null) => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const createAuthSlice: StateCreator<
  StoreState,
  [],
  [],
  AuthSlice
> = (set, get) => ({
  user: null,
  token: localStorage.getItem("contained_auth_token"),
  isAuthenticated: false,
  isAuthEnabled: false,
  authLoading: true,

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setToken: (token) => {
    if (token) {
      localStorage.setItem("contained_auth_token", token);
    } else {
      localStorage.removeItem("contained_auth_token");
    }
    set({ token });
  },

  logout: async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    localStorage.removeItem("contained_auth_token");
    set({ user: null, token: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    set({ authLoading: true });
    try {
      const health = await api.getSystemHealth();
      const authEnabled = !!(health as any)?.auth_enabled;
      set({ isAuthEnabled: authEnabled });

      const token = localStorage.getItem("contained_auth_token");
      if (token || !authEnabled) {
        const user = await api.getMe();
        set({ user, isAuthenticated: true });
      }
    } catch (e) {
      console.warn("Auth check error:", e);
      set({ user: null, isAuthenticated: false });
    } finally {
      set({ authLoading: false });
    }
  },
});
