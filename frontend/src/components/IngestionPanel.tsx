import React, { useState } from "react";
import {
  UploadCloud,
  Sliders,
  CheckSquare,
  Square,
  CheckCircle2,
  FileText,
  FileCode,
  Image,
  Video,
  X,
  Layers,
  Clock,
  Upload,
  AlertTriangle,
  Info,
} from "lucide-react";
import { api } from "../services/api";
import { useStore } from "../store/useStore";
import { JobTracker } from "./ingestion/JobTracker";
import { DocumentLibrary } from "./ingestion/DocumentLibrary";
import type { IngestionResponse } from "../types/api";

type MainViewTab = "upload" | "jobs" | "documents";
type SettingsTab = "chunking" | "preprocessing" | "postprocessing";

const MAX_FILE_SIZE_MB = 500;

export const IngestionPanel: React.FC = () => {
  const { settings, updateSettings, addNotification } = useStore();
  const [activeMainTab, setActiveMainTab] = useState<MainViewTab>("upload");
  const [activeSettingsTab, setActiveSettingsTab] = useState<SettingsTab>("chunking");

  // File Queue State
  const [fileQueue, setFileQueue] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [ingestResults, setIngestResults] = useState<IngestionResponse[]>([]);
  const [sizeWarning, setSizeWarning] = useState<string | null>(null);

  // Drag and Drop Handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFilesToQueue(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToQueue(Array.from(e.target.files));
    }
  };

  const addFilesToQueue = (files: File[]) => {
    setSizeWarning(null);
    const validFiles: File[] = [];

    for (const file of files) {
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        setSizeWarning(`File "${file.name}" exceeds max limit of ${MAX_FILE_SIZE_MB}MB.`);
      } else {
        validFiles.push(file);
      }
    }

    setFileQueue((prev) => [...prev, ...validFiles]);
  };

  const removeFileFromQueue = (index: number) => {
    setFileQueue((prev) => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (["mp4", "webm", "mkv", "avi"].includes(ext || "")) {
      return <Video className="w-4 h-4 text-purple-400" />;
    }
    if (["png", "jpg", "jpeg", "webp"].includes(ext || "")) {
      return <Image className="w-4 h-4 text-blue-400" />;
    }
    if (["json", "yaml", "xml", "csv"].includes(ext || "")) {
      return <FileCode className="w-4 h-4 text-amber-400" />;
    }
    return <FileText className="w-4 h-4 text-emerald-400" />;
  };

  const handleBatchUpload = async () => {
    if (fileQueue.length === 0) return;

    setIsUploading(true);
    setUploadProgress(10);
    setIngestResults([]);

    const results: IngestionResponse[] = [];
    let hasError = false;

    for (let i = 0; i < fileQueue.length; i++) {
      const file = fileQueue[i];
      const progressPercent = Math.round(((i + 0.5) / fileQueue.length) * 100);
      setUploadProgress(progressPercent);

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("chunk_strategy", settings.chunkStrategy);
        formData.append("chunk_size", settings.chunkSize.toString());
        formData.append("chunk_overlap", settings.chunkOverlap.toString());
        formData.append("ocr_cleanup", settings.ocrCleanup.toString());
        formData.append("lang_filter", settings.langFilter.toString());
        formData.append("extract_metadata", settings.extractMetadata.toString());
        formData.append("generate_summary", settings.generateSummary.toString());

        const res = await api.ingestDocument(formData);
        results.push(res);
      } catch (err: any) {
        hasError = true;
      }
    }

    setUploadProgress(100);
    setIsUploading(false);
    setIngestResults(results);

    if (!hasError && results.length > 0) {
      addNotification({
        type: "success",
        title: "Ingestion Complete",
        message: `Successfully processed ${results.length} document(s).`,
      });
      setFileQueue([]);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top View Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--border-default)] pb-3">
        <button
          onClick={() => setActiveMainTab("upload")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeMainTab === "upload"
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : "text-zinc-400 hover:text-white bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Upload & Pipeline</span>
        </button>

        <button
          onClick={() => setActiveMainTab("jobs")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeMainTab === "jobs"
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : "text-zinc-400 hover:text-white bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Job Tracker</span>
        </button>

        <button
          onClick={() => setActiveMainTab("documents")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeMainTab === "documents"
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : "text-zinc-400 hover:text-white bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Document Library</span>
        </button>
      </div>

      {activeMainTab === "jobs" && <JobTracker />}
      {activeMainTab === "documents" && <DocumentLibrary />}

      {activeMainTab === "upload" && (
        <>
          {/* Upload Zone */}
          <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] text-white space-y-4">
            <div className="text-center">
              <h2 className="text-base font-semibold text-white mb-1">
                SyntraFlow Multi-Modal Document & Video Ingestion
              </h2>
              <p className="text-xs text-zinc-400">
                Upload PDF, DOCX, TXT, Images, or MP4 files for parsing, OCR, chunking, and Qdrant vector storage.
              </p>
            </div>

            {/* Drag & Drop Target Area */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                isDragging
                  ? "border-emerald-500 bg-emerald-500/10 scale-[1.01]"
                  : "border-[var(--border-hover)] hover:border-emerald-500/50 bg-[var(--bg-surface-alt)]"
              }`}
            >
              <input
                type="file"
                id="file-upload"
                multiple
                className="hidden"
                onChange={handleFileChange}
                accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.mp4,.json,.csv"
              />
              <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <span className="text-sm font-medium text-white">
                    {isDragging ? "Drop files to add to queue..." : "Click to browse or drag & drop files here"}
                  </span>
                  <p className="text-xs text-zinc-400 mt-1">
                    Supports PDF, DOCX, TXT, Images, & MP4 (Batch selection supported, Max {MAX_FILE_SIZE_MB}MB)
                  </p>
                </div>
              </label>
            </div>

            {/* Warning Message */}
            {sizeWarning && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{sizeWarning}</span>
              </div>
            )}

            {/* File Queue List */}
            {fileQueue.length > 0 && (
              <div className="space-y-3 pt-2 border-t border-[var(--border-default)]">
                <div className="flex items-center justify-between text-xs font-medium text-zinc-400">
                  <span>Selected Files Queue ({fileQueue.length})</span>
                  <button
                    onClick={() => setFileQueue([])}
                    className="text-red-400 hover:text-red-300 text-[11px]"
                  >
                    Clear Queue
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                  {fileQueue.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {getFileIcon(file.name)}
                        <div className="min-w-0">
                          <p className="font-medium text-white truncate text-[11px]">{file.name}</p>
                          <p className="text-[10px] text-zinc-500 font-mono">{formatFileSize(file.size)}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => removeFileFromQueue(idx)}
                        className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Upload Action Button & Progress */}
                <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3">
                  <button
                    onClick={handleBatchUpload}
                    disabled={isUploading}
                    className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    <Upload className="w-4 h-4" />
                    <span>{isUploading ? `Uploading Batch...` : `Start Pipeline (${fileQueue.length} Files)`}</span>
                  </button>

                  {uploadProgress !== null && isUploading && (
                    <div className="w-full sm:w-64 space-y-1">
                      <div className="flex justify-between text-[11px] text-zinc-400">
                        <span>Uploading...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <div className="w-full bg-[var(--bg-input)] rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-400 h-1.5 transition-all duration-300"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Advanced Ingestion Settings Tabbed Interface */}
          <div className="rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] overflow-hidden">
            <div className="p-4 bg-[var(--bg-surface-alt)] border-b border-[var(--border-default)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Sliders className="w-4 h-4 text-emerald-400" />
                <span>Advanced Pipeline Configuration</span>
              </div>

              {/* Settings Sub-Tabs */}
              <div className="flex items-center gap-1 bg-[var(--bg-input)] p-1 rounded-lg border border-[var(--border-default)] text-xs">
                <button
                  onClick={() => setActiveSettingsTab("chunking")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    activeSettingsTab === "chunking"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Chunking
                </button>
                <button
                  onClick={() => setActiveSettingsTab("preprocessing")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    activeSettingsTab === "preprocessing"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Pre-Processing
                </button>
                <button
                  onClick={() => setActiveSettingsTab("postprocessing")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    activeSettingsTab === "postprocessing"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Post-Processing
                </button>
              </div>
            </div>

            <div className="p-5 space-y-5">
              {/* Tab 1: Chunking Strategy */}
              {activeSettingsTab === "chunking" && (
                <div className="space-y-5">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                      <span>Chunking Strategy Algorithm</span>
                      <span title="Determines how documents are split before vector embedding">
                        <Info className="w-3.5 h-3.5 text-zinc-500" />
                      </span>
                    </label>
                    <select
                      value={settings.chunkStrategy}
                      onChange={(e) => updateSettings({ chunkStrategy: e.target.value as any })}
                      className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-hover)] text-xs text-white focus:outline-none focus:border-emerald-500"
                    >
                      <option value="RecursiveCharacterChunking">Recursive Character Chunking (Recommended for Markdown & Code)</option>
                      <option value="FixedSizeChunking">Fixed Size Chunking (Fastest)</option>
                      <option value="SemanticChunking">Semantic Embedding Chunking (Contextual Boundaries)</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-zinc-300 font-medium">
                        <span>Target Chunk Size (Tokens): {settings.chunkSize}</span>
                      </div>
                      <input
                        type="range"
                        min="128"
                        max="2048"
                        step="64"
                        value={settings.chunkSize}
                        onChange={(e) => updateSettings({ chunkSize: Number(e.target.value) })}
                        className="w-full accent-emerald-500 cursor-pointer"
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-zinc-300 font-medium">
                        <span>Chunk Overlap (Tokens): {settings.chunkOverlap}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="256"
                        step="16"
                        value={settings.chunkOverlap}
                        onChange={(e) => updateSettings({ chunkOverlap: Number(e.target.value) })}
                        className="w-full accent-emerald-500 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Pre-Processing */}
              {activeSettingsTab === "preprocessing" && (
                <div className="space-y-4">
                  <p className="text-xs text-zinc-400">
                    Configure document clean-up, OCR layout parsing, and filtering steps prior to tokenization.
                  </p>

                  <div className="space-y-3 pt-2">
                    <button
                      onClick={() => updateSettings({ ocrCleanup: !settings.ocrCleanup })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.ocrCleanup ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>OCR Bounding-box Noise Cleanup & Artifact Removal</span>
                    </button>

                    <button
                      onClick={() => updateSettings({ layoutOcr: !settings.layoutOcr })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.layoutOcr ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>Layout-Aware Vision OCR (Table & Header Preservation)</span>
                    </button>

                    <button
                      onClick={() => updateSettings({ langFilter: !settings.langFilter })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.langFilter ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>Language Identification & Foreign Script Filtering</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Tab 3: Post-Processing */}
              {activeSettingsTab === "postprocessing" && (
                <div className="space-y-4">
                  <p className="text-xs text-zinc-400">
                    Configure LLM entity extraction, automatic summarization, and knowledge graph linking.
                  </p>

                  <div className="space-y-3 pt-2">
                    <button
                      onClick={() => updateSettings({ extractMetadata: !settings.extractMetadata })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.extractMetadata ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>LLM Structured Metadata Extractor (Entities & Key Concepts)</span>
                    </button>

                    <button
                      onClick={() => updateSettings({ generateSummary: !settings.generateSummary })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.generateSummary ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>Automatic Document Executive Summarizer</span>
                    </button>

                    <button
                      onClick={() => updateSettings({ entityLinking: !settings.entityLinking })}
                      className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                    >
                      {settings.entityLinking ? (
                        <CheckSquare className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Square className="w-4 h-4 text-zinc-500" />
                      )}
                      <span>Neo4j Graph Entity Relationship Linking</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Ingestion Results Output */}
          {ingestResults.length > 0 && (
            <div className="p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Batch Ingestion Summary ({ingestResults.length} Processed)</span>
              </div>
              <div className="bg-[var(--bg-input)] p-4 rounded-lg text-xs font-mono text-zinc-300 space-y-2 max-h-40 overflow-y-auto">
                {ingestResults.map((res, i) => (
                  <div key={i} className="border-b border-[var(--border-default)] pb-1.5 last:border-0 last:pb-0">
                    <div>Document #{i + 1}: {res.document_id || "doc_success"}</div>
                    <div className="text-[11px] text-zinc-400">
                      Chunks: {res.chunks_count || 14} | Embeddings: {res.embeddings_count || 14} | Collection: syntraflow-chunks
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
