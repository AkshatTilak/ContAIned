import { createContext, useContext, type ReactNode } from "react";
import type { Hub, HubRole } from "../../types/api";

export type { HubRole };

export type HubAction =
  | "view"
  | "run_readonly"
  | "create_resource"
  | "edit_resource"
  | "execute"
  | "delete_resource"
  | "manage_datastores"
  | "manage_members"
  | "manage_links"
  | "rename_hub"
  | "archive_hub"
  | "transfer_ownership"
  | "hard_delete_hub";

export interface HubContextValue {
  hub: Hub | null;
  hubRole: HubRole | null;
  isPlatformAdmin: boolean;
  isArchived: boolean;
  isLoading: boolean;
  can: (action: HubAction) => boolean;
  denyReason: (action: HubAction) => "role" | "archived" | null;
}

export const HubContext = createContext<HubContextValue>({
  hub: null,
  hubRole: null,
  isPlatformAdmin: false,
  isArchived: false,
  isLoading: true,
  can: () => false,
  denyReason: () => "role",
});

export function useHubContext(): HubContextValue {
  return useContext(HubContext);
}

export interface HubProviderProps {
  value: HubContextValue;
  children: ReactNode;
}

export function HubProvider({ value, children }: HubProviderProps) {
  return <HubContext.Provider value={value}>{children}</HubContext.Provider>;
}
