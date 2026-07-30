import type { StateCreator } from "zustand";
import type { Hub, HubMember, HubLink, HubType } from "../types/api";

export interface HubSliceState {
  hubsByType: Record<HubType, Hub[]>;
  hubsById: Record<string, Hub>;
  activeHubId: string | null;
  membersByHub: Record<string, HubMember[]>;
  linksByHub: Record<string, HubLink[]>;
  hubListStatus: "idle" | "loading" | "ready" | "error";
  hubListError: string | null;
}

export interface HubSliceActions {
  setActiveHub: (hubId: string | null) => void;
  setHubs: (hubs: Hub[]) => void;
  upsertHub: (hub: Hub) => void;
  removeHub: (hubId: string) => void;
  setMembers: (hubId: string, members: HubMember[]) => void;
  setLinks: (hubId: string, links: HubLink[]) => void;
  setHubListStatus: (status: "idle" | "loading" | "ready" | "error", error?: string | null) => void;
  evictHubData: (hubId: string) => void;
}

export type HubSlice = HubSliceState & HubSliceActions;

export const createHubSlice: StateCreator<HubSlice, [], [], HubSlice> = (set) => ({
  hubsByType: {
    ingestion: [],
    agent: [],
    workflow: [],
    eval: [],
  },
  hubsById: {},
  activeHubId: null,
  membersByHub: {},
  linksByHub: {},
  hubListStatus: "idle",
  hubListError: null,

  setActiveHub: (hubId) => set({ activeHubId: hubId }),

  setHubs: (hubs) => {
    const hubsByType: Record<HubType, Hub[]> = {
      ingestion: [],
      agent: [],
      workflow: [],
      eval: [],
    };
    const hubsById: Record<string, Hub> = {};

    for (const h of hubs) {
      hubsById[h.id] = h;
      if (hubsByType[h.hub_type]) {
        hubsByType[h.hub_type].push(h);
      }
    }

    set({
      hubsByType,
      hubsById,
      hubListStatus: "ready",
      hubListError: null,
    });
  },

  upsertHub: (hub) =>
    set((state) => {
      const updatedById = { ...state.hubsById, [hub.id]: hub };
      const typeList = state.hubsByType[hub.hub_type] || [];
      const filtered = typeList.filter((h) => h.id !== hub.id);
      const updatedByType = {
        ...state.hubsByType,
        [hub.hub_type]: [...filtered, hub],
      };
      return {
        hubsById: updatedById,
        hubsByType: updatedByType,
      };
    }),

  removeHub: (hubId) =>
    set((state) => {
      const hub = state.hubsById[hubId];
      if (!hub) return state;

      const { [hubId]: _, ...newById } = state.hubsById;
      const newTypeList = (state.hubsByType[hub.hub_type] || []).filter((h) => h.id !== hubId);

      return {
        hubsById: newById,
        hubsByType: {
          ...state.hubsByType,
          [hub.hub_type]: newTypeList,
        },
        activeHubId: state.activeHubId === hubId ? null : state.activeHubId,
      };
    }),

  setMembers: (hubId, members) =>
    set((state) => ({
      membersByHub: { ...state.membersByHub, [hubId]: members },
    })),

  setLinks: (hubId, links) =>
    set((state) => ({
      linksByHub: { ...state.linksByHub, [hubId]: links },
    })),

  setHubListStatus: (status, error = null) =>
    set({
      hubListStatus: status,
      hubListError: error,
    }),

  evictHubData: (hubId) =>
    set((state) => {
      const { [hubId]: _m, ...newMembers } = state.membersByHub;
      const { [hubId]: _l, ...newLinks } = state.linksByHub;
      return {
        membersByHub: newMembers,
        linksByHub: newLinks,
      };
    }),
});
