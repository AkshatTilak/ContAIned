import React, { useState } from "react";
import { Server, Database, Share2, Activity, ShieldCheck, Layers, Cpu } from "lucide-react";
import { EmbeddedQdrantUI } from "./infrastructure/EmbeddedQdrantUI";
import { EmbeddedNeo4jUI } from "./infrastructure/EmbeddedNeo4jUI";
import { SystemMetrics } from "./SystemMetrics";
import { useStore } from "../store/useStore";

interface InfrastructurePageProps {
  systemHealth?: any;
  modelRegistry?: any;
  onRefresh?: () => void;
}

export const InfrastructurePage: React.FC<InfrastructurePageProps> = ({
  systemHealth,
  modelRegistry,
  onRefresh,
}) => {
  // Tab State: "qdrant" | "neo4j" | "system"
  const [activeTab, setActiveTab] = useState<"qdrant" | "neo4j" | "system">("qdrant");

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full font-sans">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-extrabold text-white font-display">
              Infrastructure & Database UIs
            </h2>
            <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/15 px-2.5 py-0.5 rounded-full border border-indigo-500/30">
              Gateway Proxy Enabled
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Access native Qdrant Vector Dashboard, Neo4j Graph Browser, and real-time system metrics directly via RBAC-protected reverse proxies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>RBAC Restricted: <strong>Admin / Editor</strong></span>
          </div>
        </div>
      </div>

      {/* Infrastructure Tab Navigation Bar */}
      <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2 shrink-0">
        {[
          { id: "qdrant", label: "Qdrant Vector Dashboard", icon: Database },
          { id: "neo4j", label: "Neo4j Graph Browser", icon: Share2 },
          { id: "system", label: "System Health & Metrics", icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition-all ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-lg"
                  : "text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-elevated)]"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="mt-2">
        {activeTab === "qdrant" && <EmbeddedQdrantUI />}
        {activeTab === "neo4j" && <EmbeddedNeo4jUI />}
        {activeTab === "system" && (
          <SystemMetrics
            systemHealth={systemHealth}
            modelRegistry={modelRegistry}
            onRefresh={onRefresh}
          />
        )}
      </div>
    </div>
  );
};
