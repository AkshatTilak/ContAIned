import React, { useState } from "react";
import { Server, Database, Share2, Activity, ShieldCheck, ExternalLink, Terminal, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { EmbeddedQdrantUI } from "./infrastructure/EmbeddedQdrantUI";
import { EmbeddedNeo4jUI } from "./infrastructure/EmbeddedNeo4jUI";
import { SystemMetrics } from "./SystemMetrics";
import { CopyButton } from "./shared/CopyButton";

interface InfrastructurePageProps {
  systemHealth?: any;
  modelRegistry?: any;
  onRefresh?: () => void;
}

const NON_CORE_SERVICES = [
  {
    id: "pgadmin",
    name: "pgAdmin 4",
    description: "Web management interface for PostgreSQL database cluster.",
    port: 5050,
    url: "http://localhost:5050",
    dockerCmd: "docker run -d -p 5050:80 -e PGADMIN_DEFAULT_EMAIL=admin@contained.io -e PGADMIN_DEFAULT_PASSWORD=admin dpage/pgadmin4",
    statusKey: "database",
  },
  {
    id: "redisinsight",
    name: "Redis Insight",
    description: "GUI for monitoring and querying Redis cache & session keys.",
    port: 5540,
    url: "http://localhost:5540",
    dockerCmd: "docker run -d -p 5540:5540 redis/redisinsight:latest",
    statusKey: "redis",
  },
  {
    id: "kafkaui",
    name: "Kafka UI",
    description: "Event stream topic, partition, and consumer group manager.",
    port: 8080,
    url: "http://localhost:8080",
    dockerCmd: "docker compose up -d kafka-ui",
    statusKey: "kafka",
  },
  {
    id: "litellm",
    name: "LiteLLM Proxy Admin",
    description: "Inference server key management, routing, and usage analytics.",
    port: 4000,
    url: "http://localhost:4000",
    dockerCmd: "docker compose up -d litellm",
    statusKey: "inference_server",
  },
];

export const InfrastructurePage: React.FC<InfrastructurePageProps> = ({
  systemHealth,
  modelRegistry,
  onRefresh,
}) => {
  // Tab State: "qdrant" | "neo4j" | "non-core" | "system"
  const [activeTab, setActiveTab] = useState<"qdrant" | "neo4j" | "non-core" | "system">("qdrant");

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
            Access native Qdrant Vector Dashboard, Neo4j Graph Browser, non-core tool launch cards, and system metrics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/60 border border-indigo-800/60 text-xs font-medium text-indigo-300 transition-colors cursor-pointer"
              title="Refresh System Health & Metrics"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Refresh Metrics</span>
            </button>
          )}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>RBAC Restricted: <strong>Admin / Editor</strong></span>
          </div>
        </div>
      </div>

      {/* Infrastructure Tab Navigation Bar */}
      <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2 shrink-0 overflow-x-auto">
        {[
          { id: "qdrant", label: "Qdrant Vector Dashboard", icon: Database },
          { id: "neo4j", label: "Neo4j Graph Browser", icon: Share2 },
          { id: "non-core", label: "Non-Core Tools & Services", icon: Server },
          { id: "system", label: "System Health & Metrics", icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition-all shrink-0 ${
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
        {activeTab === "non-core" && (
          <div className="space-y-6">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-1">
              <h3 className="text-sm font-bold text-slate-100 font-display">Non-Core Support Dashboards</h3>
              <p className="text-xs text-slate-400">
                Non-core tools provide web UI access to local databases and streaming brokers. Click to launch external dashboards or copy CLI spin-up commands when containers are offline.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {NON_CORE_SERVICES.map((svc) => {
                const rawStatus = systemHealth?.services?.[svc.statusKey] || "connected";
                const isOnline = rawStatus === "connected" || rawStatus === "healthy";

                return (
                  <div
                    key={svc.id}
                    className="p-5 bg-slate-900/50 border border-slate-800 rounded-xl flex flex-col justify-between space-y-4 shadow-lg"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                            <Server className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="font-bold text-slate-100 text-base font-display">{svc.name}</h4>
                            <p className="text-xs font-mono text-slate-500">Port: {svc.port}</p>
                          </div>
                        </div>

                        <span
                          className={`flex items-center space-x-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${
                            isOnline
                              ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/40"
                              : "bg-red-950/60 text-red-400 border-red-800/40"
                          }`}
                        >
                          {isOnline ? (
                            <>
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Active</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3" />
                              <span>Offline</span>
                            </>
                          )}
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 leading-relaxed">{svc.description}</p>
                    </div>

                    <div className="space-y-3 pt-3 border-t border-slate-800/60">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-slate-500">{svc.url}</span>
                        <a
                          href={svc.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center space-x-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
                        >
                          <span>Launch Interface</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>

                      <div className="p-2.5 bg-slate-950/80 border border-slate-800/80 rounded-lg flex items-center justify-between text-xs font-mono text-slate-400 overflow-x-auto gap-2">
                        <div className="flex items-center space-x-2 truncate">
                          <Terminal className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                          <span className="truncate text-slate-300">{svc.dockerCmd}</span>
                        </div>
                        <CopyButton value={svc.dockerCmd} label="Copy Docker" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
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
