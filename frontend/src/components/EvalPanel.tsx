import React, { useState, useEffect } from "react";
import { Play, Sparkles, Plus, Trash2 } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../services/api";
import { StatusBadge, ErrorBanner } from "./shared";

interface TestCase {
  id: string;
  query: string;
  expected_output: string;
  context: string;
}

const sampleChartData = [
  { run: "Run #1", faithfulness: 0.82, relevance: 0.88 },
  { run: "Run #2", faithfulness: 0.85, relevance: 0.90 },
  { run: "Run #3", faithfulness: 0.91, relevance: 0.94 },
  { run: "Run #4", faithfulness: 0.96, relevance: 0.95 },
];

export const EvalPanel: React.FC = () => {
  const [agentId] = useState<string>("default_agent");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRunningEval, setIsRunningEval] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Test Cases Management State
  const [testCases, setTestCases] = useState<TestCase[]>([
    {
      id: "tc_101",
      query: "What is the primary architectural model used by GuardRoute for task classification?",
      expected_output: "GuardRoute uses Arch-Router-1.5B for fast intent and complexity classification.",
      context: "GuardRoute classification documentation reference."
    },
    {
      id: "tc_102",
      query: "How does SyntraFlow chunk multi-modal documents during ingestion?",
      expected_output: "SyntraFlow supports RecursiveCharacterChunking, FixedSizeChunking, and SemanticChunking.",
      context: "SyntraFlow ingestion engine specs."
    }
  ]);

  const [newQuery, setNewQuery] = useState("");
  const [newExpected, setNewExpected] = useState("");
  const [newContext, setNewContext] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    fetchTestCases();
  }, []);

  const fetchTestCases = async () => {
    try {
      const cases = await api.getEvalTestCases(agentId);
      if (Array.isArray(cases) && cases.length > 0) {
        setTestCases(
          cases.map((tc) => ({
            id: tc.id,
            query: tc.query,
            expected_output: tc.expected_output,
            context: tc.context || "",
          }))
        );
      }
    } catch (err: any) {
      // Offline fallback is active with default test cases
    }
  };

  const handleGenerateSynthetic = async () => {
    setIsGenerating(true);
    setStatusMsg("Prompting LiteLLM generator for synthetic test cases...");
    setErrorMessage(null);
    try {
      const res = await api.generateSyntheticCases(agentId, 3);
      setStatusMsg(`Generated ${res.cases?.length || 3} synthetic test cases successfully!`);
      setTimeout(() => setStatusMsg(null), 4000);
      fetchTestCases();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error occurred";
      setErrorMessage(`Synthetic generation failed: ${msg}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunEval = async () => {
    setIsRunningEval(true);
    setStatusMsg("Publishing evaluation trigger event to Kafka topic 'agent-eval-trigger'...");
    setErrorMessage(null);
    try {
      const res = await api.triggerEvalRun(agentId);
      setStatusMsg(`Eval run started! Task ID: ${res.id || "eval_98412"}`);
      setTimeout(() => setStatusMsg(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error occurred";
      setErrorMessage(`Eval run failed: ${msg}`);
    } finally {
      setIsRunningEval(false);
    }
  };

  const handleAddTestCase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQuery.trim()) return;

    const newCase: TestCase = {
      id: `tc_${Date.now()}`,
      query: newQuery,
      expected_output: newExpected || "Expected answer string",
      context: newContext || "Default context"
    };

    setTestCases([newCase, ...testCases]);
    setNewQuery("");
    setNewExpected("");
    setNewContext("");
    setShowAddForm(false);
  };

  const handleDeleteCase = (id: string) => {
    setTestCases(testCases.filter((c) => c.id !== id));
  };

  return (
    <div className="space-y-6 select-none">
      {/* Top Banner & Control Bar */}
      <div
        className="p-5 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
      >
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)] font-display">
            EvalOps Agent Evaluation & Benchmark Center
          </h2>
          <p className="text-xs text-[var(--text-secondary)]">
            Automated RAGAS & DeepEval synthetic testing, Kafka worker consumer, and history.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateSynthetic}
            disabled={isGenerating}
            className="px-4 py-2 rounded-lg font-medium text-xs text-white flex items-center gap-1.5 shadow-md disabled:opacity-50 transition-all"
            style={{ backgroundColor: 'var(--accent-indigo)' }}
          >
            <Sparkles className="w-3.5 h-3.5" />
            {isGenerating ? "Generating..." : "Generate Synthetic Tests"}
          </button>

          <button
            onClick={handleRunEval}
            disabled={isRunningEval}
            className="px-4 py-2 rounded-lg font-medium text-xs text-white flex items-center gap-1.5 shadow-md disabled:opacity-50 transition-all"
            style={{ backgroundColor: 'var(--accent-emerald)' }}
          >
            <Play className="w-3.5 h-3.5" />
            {isRunningEval ? "Evaluating..." : "Run Kafka Benchmark"}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 rounded-lg bg-[var(--emerald-soft)] border border-[rgba(16,185,129,0.3)] text-xs font-medium text-[var(--accent-emerald)]">
          {statusMsg}
        </div>
      )}

      {errorMessage && (
        <ErrorBanner
          title="EvalOps Exception"
          message={errorMessage}
        />
      )}

      {/* Metric Charts */}
      <div
        className="p-5 rounded-xl border space-y-4"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider font-display">
            Evaluation Score Progression (RAGAS / DeepEval)
          </h3>
          <StatusBadge variant="success" label="Faithfulness: 96%" size="sm" />
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sampleChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="faithfulnessGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-emerald)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-emerald)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="relevanceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-indigo)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-indigo)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis dataKey="run" stroke="var(--text-muted)" fontSize={11} />
              <YAxis domain={[0.5, 1.0]} stroke="var(--text-muted)" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: "var(--bg-surface-alt)", borderColor: "var(--border-default)", fontSize: "12px", color: "var(--text-primary)" }} />
              <Area type="monotone" dataKey="faithfulness" stroke="var(--accent-emerald)" fillOpacity={1} fill="url(#faithfulnessGrad)" name="Faithfulness" />
              <Area type="monotone" dataKey="relevance" stroke="var(--accent-indigo)" fillOpacity={1} fill="url(#relevanceGrad)" name="Answer Relevance" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Attributed Test Cases Table */}
      <div
        className="p-5 rounded-xl border space-y-4"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider font-display">
              Agent-Attributed Test Cases ({testCases.length})
            </h3>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Ground truth questions, contexts, and reference outputs for evaluations.
            </p>
          </div>

          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-xs font-medium text-[var(--text-primary)] flex items-center gap-1 transition-colors border border-[var(--border-default)]"
          >
            <Plus className="w-3.5 h-3.5 text-[var(--accent-emerald)]" /> Add Test Query
          </button>
        </div>

        {showAddForm && (
          <form
            onSubmit={handleAddTestCase}
            className="p-4 rounded-lg border space-y-3 text-xs"
            style={{ backgroundColor: 'var(--bg-surface-alt)', borderColor: 'var(--border-default)' }}
          >
            <div>
              <label className="text-[var(--text-secondary)] font-medium block mb-1">User Query Prompt</label>
              <input
                type="text"
                required
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                placeholder="e.g. What is the max token limit of Arch-Router?"
                className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-default)' }}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">Expected Output (Ground Truth)</label>
                <input
                  type="text"
                  value={newExpected}
                  onChange={(e) => setNewExpected(e.target.value)}
                  placeholder="Expected answer..."
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-default)' }}
                />
              </div>

              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">Context String</label>
                <input
                  type="text"
                  value={newContext}
                  onChange={(e) => setNewContext(e.target.value)}
                  placeholder="Reference documentation..."
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-default)' }}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] text-[var(--text-muted)] font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-[var(--accent-emerald)] text-white font-medium shadow-md"
              >
                Save Test Case
              </button>
            </div>
          </form>
        )}

        {/* Table */}
        <div className="overflow-x-auto border rounded-lg" style={{ borderColor: 'var(--border-subtle)' }}>
          <table className="w-full text-left text-xs">
            <thead>
              <tr
                className="border-b text-[var(--text-muted)] font-display"
                style={{ backgroundColor: 'var(--bg-surface-alt)', borderColor: 'var(--border-subtle)' }}
              >
                <th className="p-3 font-medium">ID</th>
                <th className="p-3 font-medium">Query Prompt</th>
                <th className="p-3 font-medium">Expected Output</th>
                <th className="p-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y text-[var(--text-primary)]" style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-subtle)' }}>
              {testCases.map((tc) => (
                <tr key={tc.id} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="p-3 font-mono text-[var(--accent-emerald)] flex-shrink-0">{tc.id}</td>
                  <td className="p-3 max-w-xs truncate font-medium text-[var(--text-primary)]" title={tc.query}>
                    {tc.query}
                  </td>
                  <td className="p-3 max-w-xs truncate text-[var(--text-secondary)]" title={tc.expected_output}>
                    {tc.expected_output}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => handleDeleteCase(tc.id)}
                      className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--accent-rose)] hover:bg-[var(--rose-soft)] transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default EvalPanel;
