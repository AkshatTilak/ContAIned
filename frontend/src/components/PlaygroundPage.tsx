import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Bot,
  User,
  Sliders,
  Sparkles,
  Copy,
  Check,
  RotateCcw,
  Edit2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Terminal,
  Loader2,
  Zap,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../services/api";
import { AttachmentZone } from "./playground/AttachmentZone";
import { SessionSidebar } from "./playground/SessionSidebar";
import type {
  PlaygroundMessage,
  PlaygroundAttachment,
  PlaygroundSession,
  ModelRegistryResponse,
} from "../types/api";

const DEFAULT_MODELS = [
  { id: "gemini/gemini-3.5-flash", name: "Google Gemini 3.5 Flash", provider: "Gemini" },
  { id: "groq/llama-3.3-70b-versatile", name: "Groq Llama 3.3 70B", provider: "Groq" },
  { id: "openrouter/google/gemini-3.5-flash:free", name: "OpenRouter Gemini Flash (Free)", provider: "OpenRouter" },
  { id: "cerebras/llama3.1-70b", name: "Cerebras Llama 3.1 70B", provider: "Cerebras" },
];

export const PlaygroundPage: React.FC = () => {
  // Session State
  const [sessions, setSessions] = useState<PlaygroundSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Playground Config State
  const [selectedModel, setSelectedModel] = useState<string>("gemini/gemini-3.5-flash");
  const [availableModels, setAvailableModels] = useState<{ id: string; name: string; provider: string }[]>(DEFAULT_MODELS);
  const [systemPrompt, setSystemPrompt] = useState<string>("You are a helpful, expert AI assistant within the ContAIned platform.");
  const [isSystemPromptOpen, setIsSystemPromptOpen] = useState(false);
  const [temperature, setTemperature] = useState<number>(0.7);
  const [maxTokens, setMaxTokens] = useState<number>(1000);
  const [isParamsOpen, setIsParamsOpen] = useState(false);

  // Messages & Attachments
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [attachments, setAttachments] = useState<PlaygroundAttachment[]>([]);
  const [inputPrompt, setInputPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load Sessions and Models on Mount
  useEffect(() => {
    fetchSessions();
    fetchModelRegistry();
  }, []);

  // Auto-scroll to bottom on message updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  const fetchModelRegistry = async () => {
    try {
      const reg: ModelRegistryResponse = await api.getModels();
      const items: { id: string; name: string; provider: string }[] = [];
      Object.values(reg).forEach((roleObj) => {
        if (roleObj.active) {
          items.push({
            id: roleObj.active.model_id,
            name: roleObj.active.display_name,
            provider: roleObj.active.provider,
          });
        }
        roleObj.available?.forEach((entry) => {
          if (!items.some((m) => m.id === entry.model_id)) {
            items.push({
              id: entry.model_id,
              name: entry.display_name,
              provider: entry.provider,
            });
          }
        });
      });
      if (items.length > 0) {
        setAvailableModels(items);
      }
    } catch {
      // Keep default models on error
    }
  };

  const fetchSessions = async () => {
    try {
      const list = await api.listPlaygroundSessions();
      setSessions(list);
    } catch (e) {
      console.warn("Could not load sessions:", e);
    }
  };

  // Session Handlers
  const handleNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setAttachments([]);
    setSystemPrompt("You are a helpful, expert AI assistant within the ContAIned platform.");
    setInputPrompt("");
  };

  const handleSelectSession = (id: string) => {
    const s = sessions.find((item) => item.id === id);
    if (s) {
      setActiveSessionId(s.id);
      setSelectedModel(s.model_id || "gemini/gemini-3.5-flash");
      setSystemPrompt(s.system_prompt || "");
      setMessages(s.messages || []);
      setAttachments(s.attachments || []);
      setTemperature(s.temperature ?? 0.7);
      setMaxTokens(s.max_tokens ?? 1000);
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await api.deletePlaygroundSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        handleNewSession();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const handleRenameSession = async (id: string, newName: string) => {
    try {
      const updated = await api.updatePlaygroundSession(id, { name: newName });
      setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, name: updated.name } : s)));
    } catch (err) {
      console.error("Failed to rename session:", err);
    }
  };

  const saveCurrentSession = async (updatedMsgs: PlaygroundMessage[]) => {
    try {
      const payload = {
        model_id: selectedModel,
        system_prompt: systemPrompt,
        messages: updatedMsgs,
        attachments: attachments,
        temperature: temperature,
        max_tokens: maxTokens,
      };

      if (activeSessionId) {
        const updated = await api.updatePlaygroundSession(activeSessionId, payload);
        setSessions((prev) => prev.map((s) => (s.id === activeSessionId ? updated : s)));
      } else {
        const created = await api.createPlaygroundSession(payload);
        setActiveSessionId(created.id);
        setSessions((prev) => [created, ...prev]);
      }
    } catch (e) {
      console.warn("Session auto-save failed:", e);
    }
  };

  // Upload Handler
  const handleUploadFile = async (file: File) => {
    setIsUploading(true);
    try {
      const res = await api.uploadPlaygroundFile(file);
      const newAtt: PlaygroundAttachment = {
        attachment_id: res.attachment_id,
        filename: res.filename,
        file_type: res.file_type,
        extracted_text_preview: res.extracted_text_preview,
        created_at: res.created_at,
      };
      setAttachments((prev) => [...prev, newAtt]);
    } catch (e: any) {
      console.error("File upload error:", e);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveAttachment = async (id: string) => {
    try {
      await api.deletePlaygroundAttachment(id);
    } catch {
      // ignore
    }
    setAttachments((prev) => prev.filter((a) => a.attachment_id !== id));
  };

  // Chat Execution Handler
  const handleSendMessage = async (customPrompt?: string) => {
    const promptToSend = customPrompt || inputPrompt;
    if (!promptToSend.trim() || isGenerating) return;

    const attachmentIds = attachments.map((a) => a.attachment_id);

    const userMessage: PlaygroundMessage = {
      role: "user",
      content: promptToSend.trim(),
      tokens: Math.ceil(promptToSend.length / 4),
      attachment_ids: attachmentIds.length > 0 ? attachmentIds : undefined,
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    if (!customPrompt) setInputPrompt("");
    setIsGenerating(true);

    try {
      const res = await api.playgroundChat({
        model_id: selectedModel,
        messages: newMessages,
        system_prompt: systemPrompt,
        temperature: temperature,
        max_tokens: maxTokens,
        attachment_ids: attachmentIds,
      });

      const assistantMessage: PlaygroundMessage = {
        role: "assistant",
        content: res.response || "No response received.",
        tokens: res.output_tokens || Math.ceil((res.response || "").length / 4),
      };

      const finalMessages = [...newMessages, assistantMessage];
      setMessages(finalMessages);
      setAttachments([]); // Clear current attachments after message sent
      await saveCurrentSession(finalMessages);
    } catch (err: any) {
      const errorMessage: PlaygroundMessage = {
        role: "assistant",
        content: `Error: ${err.message || "Failed to generate completion"}`,
      };
      setMessages([...newMessages, errorMessage]);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="flex h-full w-full bg-[#080809] overflow-hidden rounded-2xl border border-[var(--border-default)] shadow-2xl">
      {/* Session Navigation Sidebar */}
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      {/* Main Playground Workspace */}
      <div className="flex-1 flex flex-col min-w-0 bg-gradient-to-b from-[#0a0b0e] to-[#080809]">
        {/* Playground Top Bar */}
        <div className="p-4 border-b border-[var(--border-default)] bg-[var(--bg-input)]/80 backdrop-blur-md flex flex-wrap items-center justify-between gap-4 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-base text-white font-display flex items-center gap-2">
                Model Playground
                <span className="text-[10px] uppercase font-bold text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  Interactive
                </span>
              </h2>
              <p className="text-xs text-zinc-400">
                Chat, test prompts, & process documents across any model
              </p>
            </div>
          </div>

          {/* Model Selector & Parameters Controls */}
          <div className="flex items-center gap-3">
            {/* Model Selection Dropdown */}
            <div className="relative">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-[var(--bg-elevated)] border border-[var(--border-subtle)] hover:border-emerald-500/50 rounded-xl px-3 py-2 text-xs font-semibold text-zinc-200 focus:outline-none focus:border-emerald-400 transition-colors cursor-pointer pr-8"
              >
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.provider})
                  </option>
                ))}
              </select>
            </div>

            {/* System Prompt Toggle Button */}
            <button
              onClick={() => setIsSystemPromptOpen(!isSystemPromptOpen)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                isSystemPromptOpen
                  ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-300"
                  : "bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Terminal className="w-3.5 h-3.5 text-indigo-400" />
              <span>System Prompt</span>
            </button>

            {/* Parameters Drawer Toggle Button */}
            <button
              onClick={() => setIsParamsOpen(!isParamsOpen)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                isParamsOpen
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Sliders className="w-3.5 h-3.5 text-emerald-400" />
              <span>Params</span>
            </button>
          </div>
        </div>

        {/* Collapsible System Prompt Panel */}
        <AnimatePresence>
          {isSystemPromptOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 p-4 space-y-2 overflow-hidden"
            >
              <div className="flex items-center justify-between text-xs font-semibold text-zinc-300">
                <span className="flex items-center gap-2 text-indigo-400">
                  <Terminal className="w-4 h-4" /> System Instructions
                </span>
                <span className="text-[11px] text-zinc-500">Persisted with session</span>
              </div>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="Enter system instruction prompt..."
                rows={2}
                className="w-full bg-[#0d0e12] border border-[var(--border-subtle)] rounded-xl p-3 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500/50 resize-none font-mono custom-scrollbar"
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapsible Parameters Drawer */}
        <AnimatePresence>
          {isParamsOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 p-4 grid grid-cols-1 sm:grid-cols-2 gap-6 overflow-hidden"
            >
              {/* Temperature Slider */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-zinc-300">
                  <span>Temperature: {temperature}</span>
                  <span className="text-zinc-500 font-normal">
                    {temperature < 0.3 ? "Deterministic" : temperature > 1.0 ? "Creative" : "Balanced"}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-emerald-500 bg-[var(--bg-surface)] rounded-lg cursor-pointer"
                />
              </div>

              {/* Max Tokens Slider */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-zinc-300">
                  <span>Max Response Tokens: {maxTokens}</span>
                  <span className="text-zinc-500 font-normal">{maxTokens} tokens</span>
                </div>
                <input
                  type="range"
                  min="100"
                  max="4000"
                  step="100"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 bg-[var(--bg-surface)] rounded-lg cursor-pointer"
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Message Stream Display Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-500/20 to-indigo-500/20 border border-emerald-500/30 flex items-center justify-center">
                <Sparkles className="w-8 h-8 text-emerald-400" />
              </div>
              <div className="max-w-md space-y-2">
                <h3 className="font-bold text-lg text-white">Start a Conversation</h3>
                <p className="text-xs text-zinc-400">
                  Type a prompt or attach documents below to chat with{" "}
                  <span className="text-emerald-400 font-semibold">{selectedModel.split("/").pop()}</span>.
                </p>
              </div>

              {/* Quick Prompt Starter Pills */}
              <div className="flex flex-wrap justify-center gap-2 pt-4 max-w-lg">
                {[
                  "Explain vector database indexing strategies",
                  "Compare RAG vs Fine-tuning for domain models",
                  "Draft a python async execution function",
                ].map((starter, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(starter)}
                    className="px-3 py-1.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] hover:border-emerald-500/40 text-xs text-zinc-300 hover:text-emerald-300 transition-all text-left"
                  >
                    "{starter}"
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const isUser = msg.role === "user";
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-3 max-w-4xl ${isUser ? "ml-auto justify-end" : "mr-auto justify-start"}`}
                >
                  {!isUser && (
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-1 shadow-md">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`space-y-1.5 flex-1 max-w-2xl ${isUser ? "items-end" : "items-start"}`}>
                    <div
                      className={`p-4 rounded-2xl text-xs leading-relaxed transition-all shadow-md ${
                        isUser
                          ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-100 rounded-tr-none ml-auto"
                          : "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-zinc-200 rounded-tl-none"
                      }`}
                    >
                      <div className="whitespace-pre-wrap font-sans">{msg.content}</div>
                    </div>

                    {/* Meta bar under message */}
                    <div
                      className={`flex items-center gap-2 text-[10px] text-zinc-500 px-1 ${
                        isUser ? "justify-end" : "justify-start"
                      }`}
                    >
                      {msg.tokens && <span>{msg.tokens} tokens</span>}
                      <button
                        onClick={() => copyToClipboard(msg.content, idx)}
                        className="hover:text-zinc-300 flex items-center gap-1 transition-colors"
                      >
                        {copiedIndex === idx ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        <span>{copiedIndex === idx ? "Copied" : "Copy"}</span>
                      </button>
                      {isUser && (
                        <button
                          onClick={() => setInputPrompt(msg.content)}
                          className="hover:text-emerald-400 flex items-center gap-1 transition-colors"
                        >
                          <Edit2 className="w-3 h-3" />
                          <span>Edit</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {isUser && (
                    <div className="w-8 h-8 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 shrink-0 mt-1">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </motion.div>
              );
            })
          )}

          {isGenerating && (
            <div className="flex gap-3 max-w-4xl mr-auto">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-1 animate-pulse">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] text-xs text-zinc-400 flex items-center gap-2 rounded-tl-none">
                <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                <span>Generating completion from {selectedModel.split("/").pop()}...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Workspace Control & Prompt Input */}
        <div className="p-4 border-t border-[var(--border-default)] bg-[var(--bg-input)]/90 backdrop-blur-md space-y-3 shrink-0">
          {/* File Attachment Dropzone / List */}
          <AttachmentZone
            attachments={attachments}
            onUploadFile={handleUploadFile}
            onRemoveAttachment={handleRemoveAttachment}
            isUploading={isUploading}
          />

          {/* Prompt Textarea & Send Action */}
          <div className="relative flex items-end bg-[#0a0b0e] border border-[var(--border-subtle)] focus-within:border-emerald-500/50 rounded-2xl p-2 transition-all">
            <textarea
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Type your prompt here... (Press Enter to send, Shift+Enter for new line)"
              rows={2}
              className="w-full bg-transparent p-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none custom-scrollbar"
            />

            <button
              onClick={() => handleSendMessage()}
              disabled={!inputPrompt.trim() || isGenerating}
              className="p-3 rounded-xl bg-gradient-to-r from-emerald-500 to-indigo-600 text-white hover:opacity-90 disabled:opacity-40 transition-all shrink-0 ml-2 shadow-lg shadow-emerald-500/20"
              title="Send Prompt (Enter)"
            >
              {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
