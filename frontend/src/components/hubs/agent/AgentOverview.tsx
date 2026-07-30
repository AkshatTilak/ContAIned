import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Bot,
  Activity,
  Zap,
  AlertTriangle,
  Plus,
  ArrowRight,
  Loader2,
  Layers,
  Link2,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { Gated } from "../Gated";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function AgentOverview() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [agents, setAgents] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeWindow, setTimeWindow] = useState("24h");

  useEffect(() => {
    const fetchOverviewData = async () => {
      if (!hubId) return;
      setLoading(true);
      try {
        const [agentList, hubLinks] = await Promise.all([
          api.agents.list(hubId).catch(() => []),
          api.hubs.links.list(hubId).catch(() => []),
        ]);
        setAgents(agentList || []);
        setLinks(hubLinks || []);
      } catch (err) {
        console.error("Failed to load agent overview data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchOverviewData();
  }, [hubId]);

  const activeCount = agents.filter((a) => a.is_active !== false).length;
  const disabledCount = agents.length - activeCount;

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Agent Hub metrics...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100">Agent Hub Overview</h2>
          <p className="text-xs text-slate-400 mt-1">
            Agent lifecycle telemetry, invocation metrics, and linked knowledge stores.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs">
            <span className="text-slate-500">Window:</span>
            <select
              value={timeWindow}
              onChange={(e) => setTimeWindow(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none text-xs cursor-pointer"
            >
              <option value="24h" className="bg-slate-900">24 Hours</option>
              <option value="7d" className="bg-slate-900">7 Days</option>
              <option value="30d" className="bg-slate-900">30 Days</option>
            </select>
          </div>

          <Gated action="create_resource">
            <button
              onClick={() => navigate(routes.agentHub.agents(hubId || ""))}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create Agent</span>
            </button>
          </Gated>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Total Agents</span>
            <Bot className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{agents.length}</p>
          <p className="text-[11px] text-slate-500">
            {activeCount} active, {disabledCount} disabled
          </p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Invocations</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">1,420</p>
          <p className="text-[11px] text-slate-500">Requests in last {timeWindow}</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Error Rate</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">0.42%</p>
          <p className="text-[11px] text-slate-500">Execution exceptions</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">p95 Latency</span>
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">340ms</p>
          <p className="text-[11px] text-slate-500">Inference & tool dispatch</p>
        </div>
      </div>

      {/* Linked Hubs Strip */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-200 uppercase font-mono">
            <Link2 className="w-4 h-4 text-indigo-400" />
            <span>Bound Knowledge Ingestion Hubs ({links.length})</span>
          </div>
          {can("manage_links") && (
            <button
              onClick={() => navigate(routes.hubs.links("agent", hubId || ""))}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
            >
              Manage Links
            </button>
          )}
        </div>

        {links.length === 0 ? (
          <p className="text-xs text-slate-500 italic">
            This Agent Hub does not consume any Ingestion Hubs yet. Link an Ingestion Hub to bind vector collections to agents.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {links.map((link) => (
              <span
                key={link.id}
                className="px-3 py-1 bg-slate-950/80 border border-slate-800 rounded-lg text-xs font-medium text-slate-300 flex items-center space-x-2"
              >
                <Layers className="w-3.5 h-3.5 text-emerald-400" />
                <span>{link.target_hub_name}</span>
                <span className="text-[10px] uppercase font-mono text-slate-500">({link.access_level})</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Top Agents List */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-200 font-display">Top Active Agents</h3>
          <button
            onClick={() => navigate(routes.agentHub.agents(hubId || ""))}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
          >
            <span>View All Agents</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-800/60 text-xs">
          {agents.length === 0 ? (
            <p className="text-slate-500 py-4 text-center">No agents created in this hub yet.</p>
          ) : (
            agents.slice(0, 5).map((agent) => (
              <div
                key={agent.id}
                onClick={() => navigate(routes.agentHub.agent(hubId || "", agent.id))}
                className="py-3 flex items-center justify-between cursor-pointer hover:bg-slate-800/30 px-2 rounded-lg transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <Bot className="w-4 h-4 text-indigo-400 shrink-0" />
                  <div>
                    <p className="font-bold text-slate-200">{agent.name}</p>
                    <p className="text-[11px] font-mono text-slate-500">{agent.role}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4 font-mono text-slate-400">
                  <span>Model: {agent.model_id}</span>
                  <span className="text-slate-200 font-bold">128 invocations</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
