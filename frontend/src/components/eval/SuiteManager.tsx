import React, { useState, useEffect } from "react";
import { Plus, Database, Copy, Trash2, Edit2, Download, Upload, ChevronDown, ChevronUp, Layers, Check, X, FileText } from "lucide-react";
import { api } from "../../services/api";
import { useStore, type Agent } from "../../store/useStore";
import { LoadingSkeleton, EmptyState, ConfirmModal, useToast } from "../shared";
import { TestCaseEditor } from "./TestCaseEditor";

export const SuiteManager: React.FC = () => {
  const agents = useStore((state) => state.agents);
  const toast = useToast();

  const [suites, setSuites] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSuiteId, setExpandedSuiteId] = useState<string | null>(null);
  const [suiteCasesMap, setSuiteCasesMap] = useState<Record<string, any[]>>({});

  // Suite Create/Edit Modal State
  const [showSuiteModal, setShowSuiteModal] = useState(false);
  const [editingSuite, setEditingSuite] = useState<any | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [suiteName, setSuiteName] = useState("");
  const [suiteDescription, setSuiteDescription] = useState("");

  // Deletion confirm state
  const [deleteSuiteId, setDeleteSuiteId] = useState<string | null>(null);
  const [deleteSuiteName, setDeleteSuiteName] = useState("");

  // Import Modal state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importSuiteId, setImportSuiteId] = useState<string | null>(null);
  const [importJsonText, setImportJsonText] = useState("");

  useEffect(() => {
    fetchSuites();
  }, []);

  const fetchSuites = async () => {
    setIsLoading(true);
    try {
      const res = await api.listSuites();
      setSuites(res.suites || []);
      if (res.suites && res.suites.length > 0) {
        res.suites.forEach((s: any) => fetchCasesForSuite(s.id));
      }
    } catch (err: any) {
      toast.error("Load Failed", err.message || "Failed to fetch test suites.");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCasesForSuite = async (sId: string) => {
    try {
      const res = await api.getSuite(sId);
      setSuiteCasesMap((prev) => ({ ...prev, [sId]: res.test_cases || [] }));
    } catch {
      // Ignore background case load error
    }
  };

  const handleOpenCreateSuite = () => {
    setEditingSuite(null);
    setSelectedAgentId(agents.length > 0 ? agents[0].id : "");
    setSuiteName("");
    setSuiteDescription("");
    setShowSuiteModal(true);
  };

  const handleOpenEditSuite = (s: any) => {
    setEditingSuite(s);
    setSelectedAgentId(s.agent_id);
    setSuiteName(s.name);
    setSuiteDescription(s.description || "");
    setShowSuiteModal(true);
  };

  const handleSaveSuite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!suiteName.trim()) return;

    try {
      if (editingSuite) {
        await api.updateSuite(editingSuite.id, {
          name: suiteName,
          description: suiteDescription || undefined,
        });
        toast.success("Suite Updated", `Test suite "${suiteName}" updated.`);
      } else {
        await api.createSuite({
          agent_id: selectedAgentId,
          name: suiteName,
          description: suiteDescription || undefined,
        });
        toast.success("Suite Created", `Created new evaluation test suite "${suiteName}".`);
      }
      setShowSuiteModal(false);
      fetchSuites();
    } catch (err: any) {
      toast.error("Save Failed", err.message || "Could not save test suite.");
    }
  };

  const handleCloneSuite = async (s: any) => {
    try {
      const res = await api.cloneSuite(s.id);
      toast.success("Suite Cloned", `Created copy "${res.name}".`);
      fetchSuites();
    } catch (err: any) {
      toast.error("Clone Failed", err.message || "Could not clone suite.");
    }
  };

  const handleExportSuite = async (sId: string, sName: string) => {
    try {
      const data = await api.exportSuiteCases(sId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `eval_suite_${sName.toLowerCase().replace(/\s+/g, "_")}.json`;
      a.click();
      toast.success("Export Complete", `Exported "${sName}" dataset to JSON.`);
    } catch (err: any) {
      toast.error("Export Failed", err.message || "Could not export suite.");
    }
  };

  const confirmDeleteSuite = async () => {
    if (!deleteSuiteId) return;
    try {
      await api.deleteSuite(deleteSuiteId);
      toast.success("Suite Deleted", `Removed suite "${deleteSuiteName}".`);
      setDeleteSuiteId(null);
      fetchSuites();
    } catch (err: any) {
      toast.error("Delete Failed", err.message || "Could not delete suite.");
    }
  };

  const handleExecuteImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importSuiteId || !importJsonText.trim()) return;

    try {
      const parsed = JSON.parse(importJsonText);
      const payloadArray = Array.isArray(parsed) ? parsed : (parsed.test_cases || []);
      const res = await api.importSuiteCasesJson(importSuiteId, payloadArray);
      toast.success("Import Complete", `Successfully imported ${res.cases_imported} test cases.`);
      setShowImportModal(false);
      fetchCasesForSuite(importSuiteId);
    } catch (err: any) {
      toast.error("Import Error", err.message || "Invalid JSON payload structure.");
    }
  };

  const toggleExpand = (sId: string) => {
    setExpandedSuiteId((prev) => (prev === sId ? null : sId));
  };

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-extrabold text-white font-display flex items-center gap-2">
            Evaluation Test Suites ({suites.length})
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Manage test cases, import/export ground truth datasets, and configure suite benchmarks.
          </p>
        </div>

        <button
          onClick={handleOpenCreateSuite}
          className="px-4 py-2 rounded-xl font-bold text-xs text-white flex items-center gap-2 shadow-lg transition-all"
          style={{ backgroundColor: "var(--accent-indigo)" }}
        >
          <Plus className="w-4 h-4" /> Create Test Suite
        </button>
      </div>

      {isLoading ? (
        <LoadingSkeleton variant="card" count={2} />
      ) : suites.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No Evaluation Test Suites"
          description="Create your first test suite or import dataset test cases to benchmark platform agents."
          actionLabel="Create Test Suite"
          onAction={handleOpenCreateSuite}
        />
      ) : (
        <div className="space-y-4">
          {suites.map((s) => {
            const isExpanded = expandedSuiteId === s.id;
            const cases = suiteCasesMap[s.id] || [];
            const agent = agents.find((a) => a.id === s.agent_id);

            return (
              <div
                key={s.id}
                className="rounded-2xl border bg-[#0e0e12] overflow-hidden transition-all shadow-xl"
                style={{ borderColor: "var(--border-default)" }}
              >
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/60">
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => toggleExpand(s.id)}
                      className="p-2 rounded-lg bg-zinc-800 text-zinc-300 hover:text-white mt-0.5"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-white font-display">{s.name}</h4>
                        <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                          {cases.length} Cases
                        </span>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-1">
                        {s.description || "No description provided."}
                      </p>
                      {agent && (
                        <span className="inline-block text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 mt-2">
                          Agent: {agent.name}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 self-end md:self-auto">
                    <button
                      onClick={() => {
                        setImportSuiteId(s.id);
                        setImportJsonText("");
                        setShowImportModal(true);
                      }}
                      className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-1 text-[11px]"
                      title="Import Dataset Cases"
                    >
                      <Upload className="w-3.5 h-3.5" /> Import
                    </button>
                    <button
                      onClick={() => handleExportSuite(s.id, s.name)}
                      className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-1 text-[11px]"
                      title="Export Suite to JSON"
                    >
                      <Download className="w-3.5 h-3.5" /> Export
                    </button>
                    <button
                      onClick={() => handleCloneSuite(s)}
                      className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
                      title="Clone Suite"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleOpenEditSuite(s)}
                      className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
                      title="Edit Suite"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setDeleteSuiteId(s.id);
                        setDeleteSuiteName(s.name);
                      }}
                      className="p-1.5 text-zinc-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-colors"
                      title="Delete Suite"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="p-5 bg-black/40 border-t border-zinc-900">
                    <TestCaseEditor
                      suiteId={s.id}
                      testCases={cases}
                      onRefresh={() => fetchCasesForSuite(s.id)}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm Suite Deletion Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteSuiteId)}
        title="Delete Test Suite?"
        message={`Are you sure you want to delete "${deleteSuiteName}"? All contained test cases will be permanently removed.`}
        confirmLabel="Delete Suite"
        cancelLabel="Cancel"
        isDanger={true}
        onConfirm={confirmDeleteSuite}
        onCancel={() => setDeleteSuiteId(null)}
      />

      {/* Create / Edit Suite Modal */}
      {showSuiteModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-6">
          <div className="w-full max-w-md border rounded-2xl bg-zinc-900 border-zinc-800 shadow-2xl p-6 space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-bold text-white font-display">
                {editingSuite ? "Edit Test Suite" : "Create Test Suite"}
              </h3>
              <button onClick={() => setShowSuiteModal(false)} className="text-zinc-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveSuite} className="space-y-4">
              <div>
                <label className="text-zinc-300 block mb-1">Target Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white focus:outline-none"
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.role})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-zinc-300 block mb-1">Suite Name</label>
                <input
                  type="text"
                  required
                  value={suiteName}
                  onChange={(e) => setSuiteName(e.target.value)}
                  placeholder="e.g. Core RAG Groundedness Suite"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white focus:outline-none"
                />
              </div>

              <div>
                <label className="text-zinc-300 block mb-1">Description</label>
                <textarea
                  rows={3}
                  value={suiteDescription}
                  onChange={(e) => setSuiteDescription(e.target.value)}
                  placeholder="Optional description..."
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white focus:outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowSuiteModal(false)}
                  className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold"
                >
                  Save Suite
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk JSON Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-6">
          <div className="w-full max-w-lg border rounded-2xl bg-zinc-900 border-zinc-800 shadow-2xl p-6 space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-bold text-white font-display">Bulk Import Test Cases</h3>
              <button onClick={() => setShowImportModal(false)} className="text-zinc-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleExecuteImport} className="space-y-4">
              <div>
                <label className="text-zinc-300 block mb-1">JSON Dataset Array</label>
                <textarea
                  rows={8}
                  required
                  value={importJsonText}
                  onChange={(e) => setImportJsonText(e.target.value)}
                  placeholder={`[\n  {\n    "input_query": "Sample prompt",\n    "expected_output": "Target answer",\n    "expected_context": ["Context chunk 1"]\n  }\n]`}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white font-mono text-xs focus:outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold"
                >
                  Import Cases
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
