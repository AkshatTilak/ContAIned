import React, { useState } from "react";
import { Play, X, Zap, ShieldCheck, Check } from "lucide-react";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";
import { useToast } from "../shared";

interface RunConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunTriggered: () => void;
}

export const RunConfigModal: React.FC<RunConfigModalProps> = ({ isOpen, onClose, onRunTriggered }) => {
  const agents = useStore((state) => state.agents);
  const toast = useToast();

  const [selectedAgentId, setSelectedAgentId] = useState(agents.length > 0 ? agents[0].id : "");
  const [selectedSuiteId, setSelectedSuiteId] = useState("");
  const [framework, setFramework] = useState("both");
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([
    "faithfulness",
    "relevance",
    "hallucination",
    "toxicity",
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const availableMetrics = [
    { id: "faithfulness", label: "Faithfulness (RAGAS / DeepEval)" },
    { id: "relevance", label: "Answer Relevancy (RAGAS / DeepEval)" },
    { id: "context_recall", label: "Context Recall (RAGAS)" },
    { id: "context_precision", label: "Context Precision (RAGAS)" },
    { id: "hallucination", label: "Hallucination Metric (DeepEval)" },
    { id: "toxicity", label: "Toxicity Scanner (DeepEval)" },
    { id: "bias", label: "Demographic Bias Scanner (DeepEval)" },
  ];

  if (!isOpen) return null;

  const toggleMetric = (mId: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(mId) ? prev.filter((m) => m !== mId) : [...prev, mId]
    );
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgentId) return;

    setIsSubmitting(true);
    try {
      const res = await api.triggerEvalRunEnhanced({
        agent_id: selectedAgentId,
        suite_id: selectedSuiteId || undefined,
        framework,
        metrics: selectedMetrics,
      });

      toast.success(
        "Evaluation Run Initiated",
        `Job ${res.run_id} started via ${res.mode.toUpperCase()} dispatcher.`
      );
      onRunTriggered();
      onClose();
    } catch (err: any) {
      toast.error("Trigger Failed", err.message || "Could not initiate evaluation run.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-6 font-sans">
      <div className="w-full max-w-lg border rounded-2xl bg-zinc-900 border-zinc-800 shadow-2xl p-6 space-y-5 text-xs">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white font-display">Configure & Trigger Eval Run</h3>
              <p className="text-[11px] text-zinc-400">
                Select target agent, framework engine, and metrics to execute.
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-white p-1 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleExecute} className="space-y-4">
          <div>
            <label className="text-zinc-300 font-medium block mb-1">Target Agent *</label>
            <select
              required
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white focus:outline-none focus:border-indigo-500"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.role})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-zinc-300 font-medium block mb-1">Evaluation Framework Engine</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "both", label: "Both (RAGAS + DeepEval)" },
                { id: "ragas", label: "RAGAS Engine" },
                { id: "deepeval", label: "DeepEval Engine" },
              ].map((fw) => (
                <button
                  type="button"
                  key={fw.id}
                  onClick={() => setFramework(fw.id)}
                  className={`p-2.5 rounded-xl border text-center font-bold transition-all ${
                    framework === fw.id
                      ? "bg-indigo-600/20 border-indigo-500 text-indigo-300"
                      : "bg-zinc-950 border-zinc-800 text-zinc-400"
                  }`}
                >
                  {fw.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-zinc-300 font-medium block mb-1.5">Select Metrics to Benchmark</label>
            <div className="space-y-1.5 max-h-44 overflow-y-auto custom-scrollbar pr-1">
              {availableMetrics.map((m) => {
                const isChecked = selectedMetrics.includes(m.id);
                return (
                  <button
                    type="button"
                    key={m.id}
                    onClick={() => toggleMetric(m.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-colors ${
                      isChecked
                        ? "bg-indigo-950/30 border-indigo-500/50 text-indigo-300"
                        : "bg-zinc-950 border-zinc-800 text-zinc-400"
                    }`}
                  >
                    <span>{m.label}</span>
                    {isChecked && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-zinc-800 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !selectedAgentId}
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold flex items-center gap-1.5 shadow-lg disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Zap className="w-4 h-4 animate-spin" /> Dispatching...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" /> Run Evaluation Job
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
