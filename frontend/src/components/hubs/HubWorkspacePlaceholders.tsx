/**
 * Hub workspace overview placeholders.
 *
 * These stubs allow the V6 route tree to compile while the full workspace
 * implementations land in S6-09 (Ingestion & Agent) and S6-10 (Workflow &
 * Eval). Each hub type's child routes render a consistent placeholder panel
 * that names the upcoming subtask.
 */

import { motion } from "framer-motion";
import { useHubContext } from "./HubContext";

function WorkspacePlaceholder({
  hubType,
  subtask,
}: {
  hubType: string;
  subtask: string;
}) {
  const { hub } = useHubContext();
  return (
    <motion.div
      className="workspace-placeholder"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="workspace-placeholder__badge" data-hub-type={hubType}>
        {hubType}
      </div>
      <h2 className="workspace-placeholder__title">
        {hub?.name ?? "Hub"} — {hubType.charAt(0).toUpperCase() + hubType.slice(1)} Workspace
      </h2>
      <p className="workspace-placeholder__body">
        Full workspace implementation arrives in{" "}
        <code>{subtask}</code>.
      </p>
    </motion.div>
  );
}

export function IngestionHubOverview() {
  return <WorkspacePlaceholder hubType="ingestion" subtask="S6-09a" />;
}

export function AgentHubOverview() {
  return <WorkspacePlaceholder hubType="agent" subtask="S6-09c" />;
}

export function WorkflowHubOverview() {
  return <WorkspacePlaceholder hubType="workflow" subtask="S6-10a" />;
}

export function EvalHubOverview() {
  return <WorkspacePlaceholder hubType="eval" subtask="S6-10b" />;
}
