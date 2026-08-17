import React, { useState, useRef, useEffect } from "react";
import {
  Play, X, Loader2, CheckCircle2, AlertTriangle, Terminal,
  ChevronDown, ChevronUp, Zap, Clock, XCircle,
} from "lucide-react";
import { api } from "../../../services/api";

interface NodeEvent {
  event: "node_start" | "node_end" | "run_start" | "run_end";
  data: Record<string, any>;
}

interface WorkflowRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  hubId: string;
  workflowId: string;
  workflowName: string;
}

function NodeEventRow({ evt }: { evt: NodeEvent }) {
  const [expanded, setExpanded] = useState(false);
  const isEnd = evt.event === "node_end";
  const isStart = evt.event === "node_start";
  const status = isEnd ? evt.data.status : "running";
  const statusColor =
    status === "succeeded" ? "text-emerald-400" :
    status === "failed" ? "text-rose-400" :
    "text-amber-400";
  const StatusIcon =
    status === "succeeded" ? CheckCircle2 :
    status === "failed" ? XCircle :
    Loader2;

  if (!isStart && !isEnd) return null;

  return (
    <div className="border border-slate-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-950/60 hover:bg-slate-900/60 transition-colors"
      >
        <div className="flex items-center space-x-2.5 min-w-0">
          <StatusIcon className={`w-3.5 h-3.5 shrink-0 ${statusColor} ${status === "running" ? "animate-spin" : ""}`} />
          <span className="text-xs font-mono text-slate-300 truncate">
            {isStart ? "→" : "✓"} <span className="text-slate-400">{evt.data.node_type}</span>{" "}
            <span className="text-slate-500">#{evt.data.node_id}</span>
          </span>
          {isEnd && evt.data.latency_ms != null && (
            <span className="text-[10px] font-mono text-slate-600 shrink-0">
              {Math.round(evt.data.latency_ms)}ms
            </span>
          )}
        </div>
        {isEnd && evt.data.output_preview && (
          expanded ? <ChevronUp className="w-3 h-3 text-slate-500" /> : <ChevronDown className="w-3 h-3 text-slate-500" />
        )}
      </button>
      {expanded && isEnd && evt.data.output_preview && (
        <div className="px-3 pb-3 pt-1 bg-slate-950/80">
          <pre className="text-[10px] font-mono text-emerald-300 whitespace-pre-wrap break-all max-h-32 overflow-auto custom-scrollbar">
            {evt.data.output_preview}
          </pre>
        </div>
      )}
    </div>
  );
}

export function WorkflowRunModal({
  isOpen,
  onClose,
  hubId,
  workflowId,
  workflowName,
}: WorkflowRunModalProps) {
  const [inputJson, setInputJson] = useState<string>(
    JSON.stringify({ input: "What are the core technical skills listed in the document?" }, null, 2)
  );
  const [useDraft, setUseDraft] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nodeEvents, setNodeEvents] = useState<NodeEvent[]>([]);
  const [runEndData, setRunEndData] = useState<any | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [nodeEvents]);

  // Cleanup SSE on unmount / close
  useEffect(() => {
    if (!isOpen) {
      esRef.current?.close();
      esRef.current = null;
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    setNodeEvents([]);
    setRunEndData(null);
    setRunStatus(null);
    esRef.current?.close();

    let parsedInput: any = {};
    try {
      parsedInput = JSON.parse(inputJson);
    } catch {
      setError("Invalid JSON input payload!");
      setIsRunning(false);
      return;
    }

    try {
      // 1. POST to start the run and get run_id
      const runRecord = await api.workflows.run(hubId, workflowId, {
        input: parsedInput,
        use_draft: useDraft,
        stream: false,
      });
      const runId: string = runRecord?.id || runRecord?.run_id;
      if (!runId) throw new Error("No run_id returned from server");

      // 2. Open SSE stream
      const streamUrl = api.workflows.runs.streamUrl(hubId, workflowId, runId);
      const es = new EventSource(streamUrl);
      esRef.current = es;

      const handleEvent = (eventName: string, raw: string) => {
        try {
          const data = JSON.parse(raw);
          if (eventName === "ping") {
            return;
          }
          if (eventName === "run_end") {
            setRunEndData(data);
            setRunStatus(data.status);
            setIsRunning(false);
            es.close();
          } else {
            setNodeEvents((prev) => [...prev, { event: eventName as any, data }]);
          }
        } catch {
          // ignore parse errors
        }
      };

      for (const evtName of ["run_start", "node_start", "node_end", "run_end", "ping"]) {
        es.addEventListener(evtName, (e: MessageEvent) => handleEvent(evtName, e.data));
      }

      // Fallback: generic message
      es.onmessage = (e) => {
        try {
          const frame = JSON.parse(e.data);
          if (frame.event && frame.data) handleEvent(frame.event, JSON.stringify(frame.data));
        } catch {
          // ignore
        }
      };

      es.onerror = async () => {
        es.close();
        // Check if run already reached terminal status on server
        try {
          const finishedRun = await api.workflows.runs.get(hubId, workflowId, runId);
          if (finishedRun && (finishedRun.status === "succeeded" || finishedRun.status === "failed")) {
            setRunEndData({
              run_id: finishedRun.id,
              status: finishedRun.status,
              duration_ms: finishedRun.duration_ms,
              output: finishedRun.output_json,
              error: finishedRun.error_message ? { message: finishedRun.error_message } : null,
            });
            setRunStatus(finishedRun.status);
            setIsRunning(false);
            return;
          }
        } catch {
          // fallback to error
        }
        setError("SSE stream connection lost. The run may still be completing.");
        setIsRunning(false);
      };
    } catch (err: any) {
      setError(err?.message || "Workflow execution failed!");
      setIsRunning(false);
    }
  };

  const handleGrantLink = async (targetHubId: string) => {
    if (!hubId) return;
    try {
      await api.hubs.links.create(hubId, {
        target_hub_id: targetHubId,
        access_level: "use",
      });
      setError(null);
      handleRun();
    } catch (err: any) {
      alert(err?.message || "Failed to grant link");
    }
  };

  const handleClose = () => {
    esRef.current?.close();
    esRef.current = null;
    onClose();
  };

  const statusColor =
    runStatus === "succeeded" ? "text-emerald-400" :
    runStatus === "failed" ? "text-rose-400" :
    runStatus === "cancelled" ? "text-amber-400" :
    "text-slate-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-indigo-950/60 border border-indigo-800/40 text-indigo-400">
              <Play className="w-4 h-4 fill-current" />
            </div>
            <div>
              <h3 className="text-sm font-bold font-display text-slate-100">Run Workflow Test</h3>
              <p className="text-xs font-mono text-slate-500">{workflowName}</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto custom-scrollbar flex-1">
          {/* Options */}
          <div className="flex items-center justify-between bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="use_draft"
                checked={useDraft}
                onChange={(e) => setUseDraft(e.target.checked)}
                className="w-4 h-4 rounded border-slate-800 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="use_draft" className="text-xs font-mono text-slate-300">
                Execute active draft version (unsaved graph topology)
              </label>
            </div>
          </div>

          {/* JSON Input */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-slate-400 font-mono flex items-center justify-between">
              <span>Input Payload (JSON)</span>
              <span className="text-[10px] text-slate-500">Must be valid JSON object</span>
            </label>
            <textarea
              rows={3}
              value={inputJson}
              onChange={(e) => setInputJson(e.target.value)}
              disabled={isRunning}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 custom-scrollbar disabled:opacity-50"
            />
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3 bg-red-950/60 border border-red-800/60 rounded-xl text-red-300 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
              {(error.includes("HUB_LINK_REQUIRED") || error.includes("not linked to target hub")) && (
                <button
                  onClick={() => {
                    const match = error.match(/target hub ['"]([^'"]+)['"]/i);
                    if (match?.[1]) handleGrantLink(match[1]);
                  }}
                  className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-lg transition-colors shrink-0 shadow"
                >
                  Grant Link & Retry
                </button>
              )}
            </div>
          )}

          {/* Live Execution Log */}
          {(nodeEvents.length > 0 || isRunning) && (
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Terminal className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-xs font-mono font-semibold text-slate-400">
                  Live Execution Log
                </span>
                {isRunning && (
                  <span className="flex items-center space-x-1 text-[10px] text-amber-400 font-mono">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Running…</span>
                  </span>
                )}
              </div>
              <div className="space-y-1.5 max-h-64 overflow-y-auto custom-scrollbar bg-slate-950/40 p-2 rounded-xl border border-slate-800">
                {nodeEvents.map((evt, i) => (
                  <NodeEventRow key={i} evt={evt} />
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          )}

          {/* Final Result */}
          {runEndData && (
            <div className="space-y-3 border-t border-slate-800 pt-4">
              <div className="flex items-center justify-between">
                <span className={`text-xs font-bold font-mono flex items-center space-x-1.5 ${statusColor}`}>
                  {runStatus === "succeeded" ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  <span>
                    {runStatus === "succeeded" ? "Execution Complete" : `Run ${runStatus}`}
                  </span>
                </span>
                <span className="text-[10px] font-mono text-slate-500 flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>{runEndData.duration_ms ?? "—"}ms</span>
                </span>
              </div>

              {runEndData.output && (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 max-h-48 overflow-auto custom-scrollbar">
                  <pre className="text-xs font-mono text-emerald-300 whitespace-pre-wrap">
                    {JSON.stringify(runEndData.output, null, 2)}
                  </pre>
                </div>
              )}
              {runEndData.error && (
                <div className="p-3 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs font-mono">
                  {runEndData.error.message || JSON.stringify(runEndData.error)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/50">
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-medium rounded-xl hover:bg-slate-700 transition-colors"
          >
            Close
          </button>

          <button
            onClick={handleRun}
            disabled={isRunning}
            className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg transition-colors"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Streaming Events…</span>
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                <span>Execute Workflow</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
