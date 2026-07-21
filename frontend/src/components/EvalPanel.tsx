import React, { useState, useEffect } from "react";
import { Play, Sparkles, Plus, Trash2 } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../services/api";

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
        setTestCases(cases);
      }
    } catch {
      // ignore offline fallback
    }
  };

  const handleGenerateSynthetic = async () => {
    setIsGenerating(true);
    setStatusMsg("Prompting LiteLLM generator for synthetic test cases...");
    try {
      const res = await api.generateSyntheticCases(agentId, 3);
      setStatusMsg(`Generated ${res.test_cases_count || 3} synthetic test cases successfully!`);
      setTimeout(() => setStatusMsg(null), 4000);
      fetchTestCases();
    } catch (err: any) {
      setStatusMsg(`Synthetic generation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunEval = async () => {
    setIsRunningEval(true);
    setStatusMsg("Publishing evaluation trigger event to Kafka topic 'agent-eval-trigger'...");
    try {
      const res = await api.triggerEvalRun(agentId);
      setStatusMsg(`Eval run started! Task ID: ${res.task_id || "eval_98412"}`);
      setTimeout(() => setStatusMsg(null), 4000);
    } catch (err: any) {
      setStatusMsg(`Eval run failed: ${err.message}`);
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
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white">EvalOps Agent Evaluation & Benchmark Center</h2>
          <p className="text-xs text-zinc-400">Automated RAGAS & DeepEval synthetic testing, Kafka worker consumer, and history.</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateSynthetic}
            disabled={isGenerating}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-indigo-600/20 disabled:opacity-50 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {isGenerating ? "Generating..." : "Generate Synthetic Tests"}
          </button>

          <button
            onClick={handleRunEval}
            disabled={isRunningEval}
            className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 disabled:opacity-50 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            {isRunningEval ? "Evaluating..." : "Run Kafka Benchmark"}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-medium text-emerald-400">
          {statusMsg}
        </div>
      )}

      {/* Metric Charts */}
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Evaluation Score Progression (RAGAS / DeepEval)</h3>
          <span className="text-xs text-emerald-400 font-mono">Latest Faithfulness: 96%</span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sampleChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="faithfulnessGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="relevanceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#26282d" />
              <XAxis dataKey="run" stroke="#71717a" fontSize={11} />
              <YAxis domain={[0.5, 1.0]} stroke="#71717a" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: "#181a21", borderColor: "#26282d", fontSize: "12px", color: "#fff" }} />
              <Area type="monotone" dataKey="faithfulness" stroke="#10b981" fillOpacity={1} fill="url(#faithfulnessGrad)" name="Faithfulness" />
              <Area type="monotone" dataKey="relevance" stroke="#6366f1" fillOpacity={1} fill="url(#relevanceGrad)" name="Answer Relevance" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Attributed Test Cases Table */}
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Agent-Attributed Test Cases ({testCases.length})</h3>
            <p className="text-[11px] text-zinc-400">Ground truth questions, contexts, and reference outputs for evaluations.</p>
          </div>

          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1 transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" /> Add Test Query
          </button>
        </div>

        {showAddForm && (
          <form onSubmit={handleAddTestCase} className="p-4 rounded-lg bg-[#181a21] border border-[#26282d] space-y-3 text-xs">
            <div>
              <label className="text-zinc-300 font-medium block mb-1">User Query Prompt</label>
              <input
                type="text"
                required
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                placeholder="e.g. What is the max token limit of Arch-Router?"
                className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-zinc-300 font-medium block mb-1">Expected Output (Ground Truth)</label>
                <input
                  type="text"
                  value={newExpected}
                  onChange={(e) => setNewExpected(e.target.value)}
                  placeholder="Expected answer..."
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-zinc-300 font-medium block mb-1">Context String</label>
                <input
                  type="text"
                  value={newContext}
                  onChange={(e) => setNewContext(e.target.value)}
                  placeholder="Reference documentation..."
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 rounded bg-[#1f2128] text-zinc-400 font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 font-medium text-white shadow-lg shadow-emerald-500/20"
              >
                Save Test Case
              </button>
            </div>
          </form>
        )}

        {/* Table */}
        <div className="overflow-x-auto border border-[#22252c] rounded-lg">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-[#181a21] border-b border-[#26282d] text-zinc-400">
                <th className="p-3 font-medium">ID</th>
                <th className="p-3 font-medium">Query Prompt</th>
                <th className="p-3 font-medium">Expected Output</th>
                <th className="p-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#22252c] text-zinc-300 bg-[#121316]">
              {testCases.map((tc) => (
                <tr key={tc.id} className="hover:bg-[#181a21] transition-colors">
                  <td className="p-3 font-mono text-emerald-400 flex-shrink-0">{tc.id}</td>
                  <td className="p-3 max-w-xs truncate font-medium text-white" title={tc.query}>
                    {tc.query}
                  </td>
                  <td className="p-3 max-w-xs truncate text-zinc-400" title={tc.expected_output}>
                    {tc.expected_output}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => handleDeleteCase(tc.id)}
                      className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-[#22252c] transition-colors"
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
