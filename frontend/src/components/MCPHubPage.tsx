import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plug,
  Server,
  Wrench,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Plus,
  Trash2,
  Edit3,
  Play,
  ToggleLeft,
  ToggleRight,
  Shield,
  Clock,
  Terminal,
  Search,
  ChevronDown,
  ChevronUp,
  X,
  Code2,
} from "lucide-react";

import { api } from "../services/api";
import type { MCPServer, MCPTool, MCPTestResult } from "../types/api";
import { useToast } from "./shared/Toast";

export const MCPHubPage: React.FC = () => {
  const { addToast } = useToast();
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);

  // Modal State for Adding/Editing Server
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    url: "",
    transport: "sse",
    auth_type: "none",
    auth_token: "",
  });
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Inline Tool Testing State
  const [testingTool, setTestingTool] = useState<MCPTool | null>(null);
  const [testParams, setTestParams] = useState<string>("{}");
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [isExecutingTest, setIsExecutingTest] = useState<boolean>(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [serverList, toolList] = await Promise.all([
        api.getMCPServers(),
        api.getAllMCPTools(),
      ]);
      setServers(serverList);
      setTools(toolList);
    } catch (err: any) {
      addToast(err.message || "Failed to load MCP servers and tools", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenAddModal = () => {
    setEditingServer(null);
    setFormData({
      name: "",
      url: "http://",
      transport: "sse",
      auth_type: "none",
      auth_token: "",
    });
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (server: MCPServer) => {
    setEditingServer(server);
    setFormData({
      name: server.name,
      url: server.url,
      transport: server.transport,
      auth_type: server.auth_type,
      auth_token: "",
    });
    setIsModalOpen(true);
  };

  const handleSaveServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.url) {
      addToast("Name and URL are required", "warning");
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingServer) {
        await api.updateMCPServer(editingServer.id, {
          name: formData.name,
          url: formData.url,
          transport: formData.transport,
          auth_type: formData.auth_type,
          auth_token: formData.auth_token || undefined,
        });
        addToast(`Updated server "${formData.name}"`, "success");
      } else {
        await api.createMCPServer({
          name: formData.name,
          url: formData.url,
          transport: formData.transport,
          auth_type: formData.auth_type,
          auth_token: formData.auth_token || undefined,
        });
        addToast(`Registered MCP server "${formData.name}"`, "success");
      }
      setIsModalOpen(false);
      fetchData();
    } catch (err: any) {
      addToast(err.message || "Failed to save MCP server", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteServer = async (server: MCPServer) => {
    if (server.is_internal) {
      addToast("Internal system servers cannot be deleted", "error");
      return;
    }
    if (!confirm(`Are you sure you want to delete MCP server "${server.name}"?`)) {
      return;
    }
    try {
      await api.deleteMCPServer(server.id);
      addToast(`Deleted server "${server.name}"`, "success");
      fetchData();
    } catch (err: any) {
      addToast(err.message || "Failed to delete server", "error");
    }
  };

  const handleTriggerHealth = async (server: MCPServer) => {
    try {
      const res = await api.checkMCPServerHealth(server.id);
      addToast(
        `Health check for "${server.name}": ${res.health_status.toUpperCase()}`,
        res.health_status === "healthy" ? "success" : "warning"
      );
      fetchData();
    } catch (err: any) {
      addToast(err.message || "Health check request failed", "error");
    }
  };

  const handleSyncTools = async (server: MCPServer) => {
    try {
      const synced = await api.syncServerTools(server.id);
      addToast(`Discovered ${synced.length} tools for "${server.name}"`, "success");
      fetchData();
    } catch (err: any) {
      addToast(err.message || "Tool discovery failed", "error");
    }
  };

  const handleToggleTool = async (tool: MCPTool) => {
    try {
      await api.toggleMCPTool(tool.id);
      setTools((prev) =>
        prev.map((t) => (t.id === tool.id ? { ...t, is_enabled: !t.is_enabled } : t))
      );
      addToast(
        `Tool "${tool.tool_name}" ${!tool.is_enabled ? "enabled" : "disabled"}`,
        "info"
      );
    } catch (err: any) {
      addToast(err.message || "Failed to toggle tool", "error");
    }
  };

  const handleOpenTestDrawer = (tool: MCPTool) => {
    setTestingTool(tool);
    setTestResult(null);
    // Auto-populate default sample JSON based on schema properties
    let sample: Record<string, any> = {};
    if (tool.input_schema_json?.properties) {
      Object.keys(tool.input_schema_json.properties).forEach((key) => {
        const prop = tool.input_schema_json?.properties[key];
        sample[key] = prop.default !== undefined ? prop.default : prop.type === "integer" ? 1 : "sample_value";
      });
    }
    setTestParams(JSON.stringify(sample, null, 2));
  };

  const handleExecuteTest = async () => {
    if (!testingTool) return;
    setIsExecutingTest(true);
    setTestResult(null);
    try {
      let parsedParams = {};
      try {
        parsedParams = JSON.parse(testParams);
      } catch {
        addToast("Invalid JSON parameters format", "error");
        setIsExecutingTest(false);
        return;
      }
      const res = await api.testMCPTool(
        testingTool.server_id,
        testingTool.tool_name,
        parsedParams
      );
      setTestResult(res);
      addToast(
        `Tool executed in ${res.execution_time_ms}ms`,
        res.status === "success" ? "success" : "error"
      );
    } catch (err: any) {
      addToast(err.message || "Tool execution failed", "error");
    } finally {
      setIsExecutingTest(false);
    }
  };

  const filteredServers = servers.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.url.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const healthyCount = servers.filter((s) => s.health_status === "healthy").length;
  const internalCount = servers.filter((s) => s.is_internal).length;

  return (
    <div className="space-y-8 pb-12 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute -right-10 -top-10 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex items-center gap-4 relative z-10">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-emerald-500/20 to-indigo-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-lg">
            <Plug className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-wide font-display flex items-center gap-2">
              MCP Integration Hub
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Model Context Protocol
              </span>
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Register external MCP servers, auto-discover tool schemas, test invocations, and integrate with workflow nodes.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 relative z-10 shrink-0">
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="p-2.5 rounded-xl bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-300 border border-zinc-700/50 transition-all text-sm flex items-center gap-2 font-medium"
            title="Refresh Servers & Tools"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={handleOpenAddModal}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold shadow-lg shadow-emerald-500/20 transition-all text-sm flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add External Server
          </button>
        </div>
      </div>

      {/* Metrics Summary Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 rounded-xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-zinc-400 uppercase tracking-wider">Registered Servers</div>
            <div className="text-xl font-bold text-white mt-0.5">{servers.length}</div>
          </div>
        </div>

        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 rounded-xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-zinc-400 uppercase tracking-wider">Healthy Status</div>
            <div className="text-xl font-bold text-emerald-400 mt-0.5">{healthyCount} / {servers.length}</div>
          </div>
        </div>

        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 rounded-xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-zinc-400 uppercase tracking-wider">Internal Servers</div>
            <div className="text-xl font-bold text-white mt-0.5">{internalCount}</div>
          </div>
        </div>

        <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 rounded-xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Wrench className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-zinc-400 uppercase tracking-wider">Discovered Tools</div>
            <div className="text-xl font-bold text-white mt-0.5">{tools.length}</div>
          </div>
        </div>
      </div>

      {/* Search Bar & Filter */}
      <div className="flex items-center gap-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] px-4 py-2.5 rounded-xl">
        <Search className="w-4 h-4 text-zinc-400 shrink-0" />
        <input
          type="text"
          placeholder="Filter servers by name or URL..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-transparent border-none text-sm text-white placeholder-zinc-500 focus:outline-none w-full"
        />
      </div>

      {/* Server List Cards */}
      {isLoading ? (
        <div className="text-center py-16 text-zinc-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
          <span>Loading registered MCP servers and tools...</span>
        </div>
      ) : filteredServers.length === 0 ? (
        <div className="text-center py-16 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl p-8">
          <Plug className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-white">No MCP Servers Found</h3>
          <p className="text-sm text-zinc-400 mt-1 max-w-md mx-auto">
            {searchQuery ? "No servers matched your search filter." : "Click 'Add External Server' to register an MCP server endpoint."}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {filteredServers.map((server) => {
            const serverTools = tools.filter((t) => t.server_id === server.id);
            const isExpanded = selectedServerId === server.id;

            return (
              <motion.div
                key={server.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl overflow-hidden shadow-lg transition-all"
              >
                {/* Server Header Bar */}
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] bg-zinc-900/40">
                  <div className="flex items-center gap-3.5 min-w-0">
                    {/* Health Dot */}
                    <div
                      className={`w-3.5 h-3.5 rounded-full shrink-0 shadow-md ${
                        server.health_status === "healthy"
                          ? "bg-emerald-400 shadow-emerald-500/50"
                          : server.health_status === "unhealthy"
                          ? "bg-rose-500 shadow-rose-500/50"
                          : "bg-amber-400 shadow-amber-500/50"
                      }`}
                      title={`Health: ${server.health_status}`}
                    />

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-bold text-white font-display truncate">
                          {server.name}
                        </h3>

                        {server.is_internal && (
                          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/30">
                            Internal
                          </span>
                        )}

                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700">
                          {server.transport}
                        </span>

                        {server.auth_type !== "none" && (
                          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
                            {server.auth_type}
                          </span>
                        )}
                      </div>
                      <div className="text-xs font-mono text-zinc-400 mt-1 truncate">
                        {server.url}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0 flex-wrap">
                    <button
                      onClick={() => handleTriggerHealth(server)}
                      className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-300 border border-zinc-700/50 flex items-center gap-1.5 transition-all"
                      title="Run manual health check"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Health Check
                    </button>

                    <button
                      onClick={() => handleSyncTools(server)}
                      className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-xs font-medium text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 transition-all"
                      title="Discover & sync tools"
                    >
                      <Wrench className="w-3.5 h-3.5" />
                      Sync Tools ({serverTools.length})
                    </button>

                    <button
                      onClick={() => handleOpenEditModal(server)}
                      className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/50 transition-all"
                      title="Edit Server Config"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => handleDeleteServer(server)}
                      disabled={server.is_internal}
                      className={`p-1.5 rounded-lg border transition-all ${
                        server.is_internal
                          ? "opacity-30 cursor-not-allowed bg-zinc-800 text-zinc-500 border-zinc-800"
                          : "bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border-rose-500/30"
                      }`}
                      title={server.is_internal ? "Internal server cannot be deleted" : "Delete Server"}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => setSelectedServerId(isExpanded ? null : server.id)}
                      className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/50 transition-all ml-1"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Collapsible Tools View */}
                <div className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-xs uppercase font-bold tracking-wider text-zinc-400 flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-emerald-400" />
                      Discovered Tools ({serverTools.length})
                    </h4>
                  </div>

                  {serverTools.length === 0 ? (
                    <div className="text-xs text-zinc-500 bg-zinc-900/50 p-4 rounded-xl border border-zinc-800 text-center">
                      No tools discovered yet. Click "Sync Tools" above to discover functions from this MCP server.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {serverTools.map((tool) => (
                        <div
                          key={tool.id}
                          className="bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 rounded-xl p-4 transition-all flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between gap-2 mb-1.5">
                              <span className="font-mono text-sm font-semibold text-emerald-400">
                                {tool.tool_name}
                              </span>

                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleToggleTool(tool)}
                                  className="text-zinc-400 hover:text-white transition-colors"
                                  title={tool.is_enabled ? "Disable Tool" : "Enable Tool"}
                                >
                                  {tool.is_enabled ? (
                                    <ToggleRight className="w-6 h-6 text-emerald-400" />
                                  ) : (
                                    <ToggleLeft className="w-6 h-6 text-zinc-600" />
                                  )}
                                </button>
                              </div>
                            </div>

                            <p className="text-xs text-zinc-400 line-clamp-2 mb-3">
                              {tool.description || "No description provided."}
                            </p>
                          </div>

                          <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between">
                            <span className="text-[10px] text-zinc-500 font-mono">
                              Synced {new Date(tool.last_synced).toLocaleTimeString()}
                            </span>

                            <button
                              onClick={() => handleOpenTestDrawer(tool)}
                              className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1.5 transition-all"
                            >
                              <Play className="w-3 h-3 fill-emerald-400" />
                              Test Inline
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Add / Edit Server Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 relative"
            >
              <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-4">
                <h3 className="text-lg font-bold text-white font-display flex items-center gap-2">
                  <Plug className="w-5 h-5 text-emerald-400" />
                  {editingServer ? "Edit MCP Server" : "Register External MCP Server"}
                </h3>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleSaveServer} className="space-y-4 text-sm">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">Server Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Weather MCP Service"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2 text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">Server URL *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. http://localhost:8012 or https://mcp.example.com"
                    value={formData.url}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2 text-white focus:outline-none focus:border-emerald-500 font-mono text-xs"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Transport</label>
                    <select
                      value={formData.transport}
                      onChange={(e) => setFormData({ ...formData, transport: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2 text-white focus:outline-none focus:border-emerald-500"
                    >
                      <option value="sse">SSE (Server-Sent Events)</option>
                      <option value="stdio">Stdio Process</option>
                      <option value="streamable_http">Streamable HTTP</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Auth Type</label>
                    <select
                      value={formData.auth_type}
                      onChange={(e) => setFormData({ ...formData, auth_type: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2 text-white focus:outline-none focus:border-emerald-500"
                    >
                      <option value="none">None</option>
                      <option value="bearer">Bearer Token</option>
                      <option value="api_key">API Key</option>
                    </select>
                  </div>
                </div>

                {formData.auth_type !== "none" && (
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Auth Token (Encrypted at rest)</label>
                    <input
                      type="password"
                      placeholder="Enter token string..."
                      value={formData.auth_token}
                      onChange={(e) => setFormData({ ...formData, auth_token: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2 text-white focus:outline-none focus:border-emerald-500 font-mono text-xs"
                    />
                  </div>
                )}

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-subtle)]">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-semibold flex items-center gap-1.5"
                  >
                    {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : null}
                    {editingServer ? "Update Server" : "Save Server"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Inline Tool Testing Drawer Modal */}
      <AnimatePresence>
        {testingTool && (
          <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/70 backdrop-blur-sm p-4">
            <motion.div
              initial={{ x: 300, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 300, opacity: 0 }}
              className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-xl h-full max-h-[90vh] flex flex-col shadow-2xl p-6 relative overflow-hidden"
            >
              <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-4 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <Terminal className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white font-display">
                      Test Tool: <span className="font-mono text-emerald-400">{testingTool.tool_name}</span>
                    </h3>
                    <p className="text-xs text-zinc-400">{testingTool.server_name}</p>
                  </div>
                </div>
                <button
                  onClick={() => setTestingTool(null)}
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto custom-scrollbar py-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">Description</label>
                  <p className="text-xs text-zinc-400 bg-zinc-900 p-3 rounded-xl border border-zinc-800">
                    {testingTool.description || "No description provided."}
                  </p>
                </div>

                {testingTool.input_schema_json && (
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">Expected Input Schema</label>
                    <pre className="text-[11px] font-mono text-zinc-300 bg-zinc-950 p-3 rounded-xl border border-zinc-800 overflow-x-auto max-h-36 custom-scrollbar">
                      {JSON.stringify(testingTool.input_schema_json, null, 2)}
                    </pre>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">JSON Parameters Input</label>
                  <textarea
                    rows={6}
                    value={testParams}
                    onChange={(e) => setTestParams(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 font-mono text-xs text-emerald-400 focus:outline-none focus:border-emerald-500 custom-scrollbar"
                  />
                </div>

                {testResult && (
                  <div className="space-y-2 pt-2 border-t border-[var(--border-subtle)]">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-zinc-300">Execution Result</span>
                      <span className="font-mono text-zinc-400 flex items-center gap-1">
                        <Clock className="w-3 h-3 text-emerald-400" />
                        {testResult.execution_time_ms} ms
                      </span>
                    </div>
                    <pre className="text-[11px] font-mono text-emerald-300 bg-zinc-950 p-3 rounded-xl border border-emerald-500/30 overflow-x-auto max-h-48 custom-scrollbar">
                      {JSON.stringify(testResult.result || testResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-[var(--border-subtle)] flex items-center justify-end gap-3 shrink-0">
                <button
                  onClick={() => setTestingTool(null)}
                  className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium"
                >
                  Close
                </button>
                <button
                  onClick={handleExecuteTest}
                  disabled={isExecutingTest}
                  className="px-5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-500/20"
                >
                  {isExecutingTest ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-white" />}
                  Execute Tool
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
