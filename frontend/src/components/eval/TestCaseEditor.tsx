import React, { useState } from "react";
import { Plus, Trash2, Edit2, Check, X, FileText, Sparkles } from "lucide-react";
import { api } from "../../services/api";
import { useToast } from "../shared";

interface TestCase {
  id: string;
  input_query: string;
  expected_output?: string;
  expected_context?: string;
}

interface TestCaseEditorProps {
  suiteId: string;
  testCases: TestCase[];
  onRefresh: () => void;
}

export const TestCaseEditor: React.FC<TestCaseEditorProps> = ({ suiteId, testCases, onRefresh }) => {
  const toast = useToast();
  const [showAddRow, setShowAddRow] = useState(false);
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null);

  // Add/Edit Form State
  const [inputQuery, setInputQuery] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [expectedContext, setExpectedContext] = useState("");

  const handleStartAdd = () => {
    setEditingCaseId(null);
    setInputQuery("");
    setExpectedOutput("");
    setExpectedContext("");
    setShowAddRow(true);
  };

  const handleStartEdit = (c: TestCase) => {
    setShowAddRow(false);
    setEditingCaseId(c.id);
    setInputQuery(c.input_query);
    setExpectedOutput(c.expected_output || "");
    setExpectedContext(c.expected_context || "");
  };

  const handleSaveAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;

    try {
      await api.addTestCase(suiteId, {
        input_query: inputQuery,
        expected_output: expectedOutput || undefined,
        expected_context: expectedContext || undefined,
      });
      toast.success("Test Case Created", "Added new test case to suite.");
      setShowAddRow(false);
      onRefresh();
    } catch (err: any) {
      toast.error("Save Failed", err.message || "Could not add test case.");
    }
  };

  const handleSaveEdit = async (cId: string, e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;

    try {
      await api.updateTestCase(cId, {
        input_query: inputQuery,
        expected_output: expectedOutput || undefined,
        expected_context: expectedContext || undefined,
      });
      toast.success("Test Case Updated", "Saved test case edits.");
      setEditingCaseId(null);
      onRefresh();
    } catch (err: any) {
      toast.error("Update Failed", err.message || "Could not update test case.");
    }
  };

  const handleDelete = async (cId: string) => {
    try {
      await api.deleteTestCase(cId);
      toast.success("Test Case Removed", "Deleted test case from suite.");
      onRefresh();
    } catch (err: any) {
      toast.error("Delete Failed", err.message || "Could not delete test case.");
    }
  };

  return (
    <div className="space-y-4 text-xs font-sans">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-bold text-white font-display">
            Suite Test Cases ({testCases.length})
          </span>
        </div>
        <button
          onClick={handleStartAdd}
          className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 font-bold border border-indigo-500/30 flex items-center gap-1.5 transition-all"
        >
          <Plus className="w-3.5 h-3.5" /> Add Test Case
        </button>
      </div>

      {showAddRow && (
        <form onSubmit={handleSaveAdd} className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/30 space-y-3">
          <div className="flex items-center justify-between text-indigo-300 font-bold text-[11px]">
            <span>New Test Case Definition</span>
            <button
              type="button"
              onClick={() => setShowAddRow(false)}
              className="text-zinc-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div>
            <label className="text-zinc-400 block mb-1 text-[10px]">User Input Query *</label>
            <input
              type="text"
              required
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="e.g. What is the retrieval latency requirement?"
              className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 block mb-1 text-[10px]">Expected Ground Truth Output</label>
              <textarea
                rows={2}
                value={expectedOutput}
                onChange={(e) => setExpectedOutput(e.target.value)}
                placeholder="Target expected response..."
                className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white font-mono text-xs focus:outline-none resize-none"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1 text-[10px]">Expected Context Chunks</label>
              <textarea
                rows={2}
                value={expectedContext}
                onChange={(e) => setExpectedContext(e.target.value)}
                placeholder="Ground truth context chunks (semicolon-delimited)..."
                className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white font-mono text-xs focus:outline-none resize-none"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setShowAddRow(false)}
              className="px-3 py-1 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold"
            >
              Save Case
            </button>
          </div>
        </form>
      )}

      {testCases.length === 0 ? (
        <div className="p-6 rounded-xl border border-dashed border-zinc-800 text-center text-zinc-500">
          No test cases defined in this suite. Click "Add Test Case" or import a dataset CSV/JSON.
        </div>
      ) : (
        <div className="space-y-2.5">
          {testCases.map((c, idx) => {
            const isEditing = editingCaseId === c.id;

            if (isEditing) {
              return (
                <form
                  key={c.id}
                  onSubmit={(e) => handleSaveEdit(c.id, e)}
                  className="p-3.5 rounded-xl bg-zinc-900 border border-indigo-500/40 space-y-2.5"
                >
                  <input
                    type="text"
                    required
                    value={inputQuery}
                    onChange={(e) => setInputQuery(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded bg-black border border-zinc-700 text-white font-mono text-xs"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <textarea
                      rows={2}
                      value={expectedOutput}
                      onChange={(e) => setExpectedOutput(e.target.value)}
                      placeholder="Expected output..."
                      className="w-full px-2.5 py-1 rounded bg-black border border-zinc-700 text-white font-mono text-xs resize-none"
                    />
                    <textarea
                      rows={2}
                      value={expectedContext}
                      onChange={(e) => setExpectedContext(e.target.value)}
                      placeholder="Expected context..."
                      className="w-full px-2.5 py-1 rounded bg-black border border-zinc-700 text-white font-mono text-xs resize-none"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingCaseId(null)}
                      className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-3 py-1 rounded bg-indigo-600 text-white font-bold flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" /> Save
                    </button>
                  </div>
                </form>
              );
            }

            return (
              <div
                key={c.id}
                className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 flex flex-col md:flex-row md:items-center justify-between gap-3 group transition-all"
              >
                <div className="space-y-1 overflow-hidden font-mono">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-indigo-400 font-bold">#{idx + 1}</span>
                    <p className="text-white font-medium text-xs truncate">{c.input_query}</p>
                  </div>
                  {(c.expected_output || c.expected_context) && (
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-zinc-400 pl-5">
                      {c.expected_output && (
                        <span>
                          <strong className="text-zinc-500">Output:</strong> {c.expected_output}
                        </span>
                      )}
                      {c.expected_context && (
                        <span>
                          <strong className="text-zinc-500">Context:</strong> {c.expected_context}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0 self-end md:self-auto">
                  <button
                    onClick={() => handleStartEdit(c)}
                    className="p-1 text-zinc-400 hover:text-white rounded hover:bg-zinc-800"
                    title="Edit Case"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => handleDelete(c.id)}
                    className="p-1 text-zinc-400 hover:text-rose-400 rounded hover:bg-rose-500/10"
                    title="Delete Case"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
