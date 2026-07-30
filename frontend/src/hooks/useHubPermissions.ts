import { useHubContext, type HubAction, type HubRole } from "../components/hubs/HubContext";

const ROLE_LADDER: Record<HubRole, number> = {
  owner: 4,
  maintainer: 3,
  contributor: 2,
  viewer: 1,
};

const MUTATING_ACTIONS: ReadonlySet<HubAction> = new Set([
  "create_resource",
  "edit_resource",
  "execute",
  "delete_resource",
  "manage_datastores",
  "manage_members",
  "manage_links",
  "rename_hub",
  "archive_hub",
  "transfer_ownership",
  "hard_delete_hub",
]);

const ACTION_MIN_ROLE: Record<HubAction, HubRole> = {
  view: "viewer",
  run_readonly: "viewer",
  create_resource: "contributor",
  edit_resource: "contributor",
  execute: "contributor",
  delete_resource: "contributor",
  manage_datastores: "contributor",
  manage_members: "maintainer",
  manage_links: "maintainer",
  rename_hub: "maintainer",
  archive_hub: "maintainer",
  transfer_ownership: "owner",
  hard_delete_hub: "owner",
};

/**
 * Pure function evaluating capability matrix without React dependency.
 */
export function evaluate(
  role: HubRole | null,
  action: HubAction,
  isArchived: boolean = false,
  isPlatformAdmin: boolean = false
): { allowed: boolean; reason: "role" | "archived" | null } {
  // Platform admin short-circuits role check to owner
  const effectiveRole: HubRole | null = isPlatformAdmin ? "owner" : role;

  if (!effectiveRole) {
    return { allowed: false, reason: "role" };
  }

  const minRole = ACTION_MIN_ROLE[action];
  const roleHasPermission = ROLE_LADDER[effectiveRole] >= ROLE_LADDER[minRole];

  if (!roleHasPermission) {
    return { allowed: false, reason: "role" };
  }

  // If role is allowed but hub is archived and action is mutating, deny due to archive status
  if (isArchived && MUTATING_ACTIONS.has(action)) {
    return { allowed: false, reason: "archived" };
  }

  return { allowed: true, reason: null };
}

/**
 * Custom hook to check permissions within a HubShell context.
 */
export function useHubPermissions() {
  const ctx = useHubContext();

  const can = (action: HubAction): boolean => {
    return evaluate(ctx.hubRole, action, ctx.isArchived, ctx.isPlatformAdmin).allowed;
  };

  const denyReason = (action: HubAction): "role" | "archived" | null => {
    return evaluate(ctx.hubRole, action, ctx.isArchived, ctx.isPlatformAdmin).reason;
  };

  return {
    hubRole: ctx.hubRole,
    isArchived: ctx.isArchived,
    isPlatformAdmin: ctx.isPlatformAdmin,
    can,
    denyReason,
  };
}
