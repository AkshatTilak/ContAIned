import React, { useState } from "react";
import { Play, Sparkles } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../services/api";

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

  const handleGenerateSynthetic = async () => {
    setIsGenerating(true);
    setStatusMsg("Prompting LiteLLM generator for synthetic test cases...");
    try {
      const res = await api.generateSyntheticCases(agentId, 5);
      setStatusMsg(`Generated ${res.test_cases_count || 5} synthetic test cases successfully!`);
      setTimeout(() => setStatusMsg(null), 4000);
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

  return (
    <div className="space-y-6">
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

      {/* Recent Eval Runs Table */}
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] space-y-3">
        <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Evaluation History</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#26282d] text-zinc-400">
                <th className="pb-2 font-medium">Run ID</th>
                <th className="pb-2 font-medium">Agent ID</th>
                <th className="pb-2 font-medium">Faithfulness</th>
                <th className="pb-2 font-medium">Relevance</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#22252c] text-zinc-300">
              <tr>
                <td className="py-2.5 font-mono text-emerald-400">eval_run_941</td>
                <td>Scatter-Gather Orchestrator</td>
                <td className="font-bold text-white">0.96</td>
                <td className="font-bold text-white">0.95</td>
                <td><span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Completed</span></td>
              </tr>
              <tr>
                <td className="py-2.5 font-mono text-emerald-400">eval_run_940</td>
                <td>Coding Subagent</td>
                <td className="font-bold text-white">0.91</td>
                <td className="font-bold text-white">0.94</td>
                <td><span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Completed</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
