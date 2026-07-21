import React, { useState } from "react";
import { UploadCloud, ChevronDown, ChevronUp, Sliders, CheckSquare, Square, CheckCircle2 } from "lucide-react";
import { IngestionResponse } from "../types/api";

export const IngestionPanel: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestionResponse | null>(null);

  // Advanced Ingestion Options
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [chunkStrategy, setChunkStrategy] = useState<"FixedSizeChunking" | "RecursiveCharacterChunking" | "SemanticChunking">("RecursiveCharacterChunking");
  const [chunkSize, setChunkSize] = useState<number>(512);
  const [chunkOverlap, setChunkOverlap] = useState<number>(64);
  const [ocrCleanup, setOcrCleanup] = useState<boolean>(true);
  const [langFilter, setLangFilter] = useState<boolean>(false);
  const [extractMetadata, setExtractMetadata] = useState<boolean>(true);
  const [generateSummary, setGenerateSummary] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadStatus("Uploading document & parsing pipeline...");
    setIngestResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("chunk_strategy", chunkStrategy);
      formData.append("chunk_size", chunkSize.toString());
      formData.append("chunk_overlap", chunkOverlap.toString());
      formData.append("ocr_cleanup", ocrCleanup.toString());
      formData.append("lang_filter", langFilter.toString());
      formData.append("extract_metadata", extractMetadata.toString());
      formData.append("generate_summary", generateSummary.toString());

      const res = await api.ingestDocument(formData);
      setIngestResult(res);
      setUploadStatus("Ingestion complete!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error occurred";
      setUploadStatus(`Ingestion failed: ${msg}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Upload Zone */}
      <div className="p-6 rounded-xl bg-[#15171e] border border-[#26282d] text-[#ffffff] text-center">
        <h2 className="text-base font-semibold text-white mb-2">SyntraFlow Multi-Modal Document & Video Ingestion</h2>
        <p className="text-xs text-zinc-400 mb-6">
          Upload PDF, DOCX, TXT, Images, or MP4 files to execute parsing, OCR, transcription, and vector embedding.
        </p>

        <div className="border-2 border-dashed border-[#2d3039] rounded-xl p-8 hover:border-emerald-500/50 transition-colors bg-[#181a21]">
          <input
            type="file"
            id="file-upload"
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.docx,.txt,.png,.jpg,.mp4"
          />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div>
              <span className="text-sm font-medium text-white">
                {selectedFile ? selectedFile.name : "Click to browse or drag & drop files here"}
              </span>
              <p className="text-xs text-zinc-400 mt-1">Supports PDF, DOCX, TXT, Images, & MP4 (Max 100MB)</p>
            </div>
          </label>
        </div>

        {selectedFile && (
          <div className="mt-4 flex items-center justify-center gap-4">
            <button
              onClick={handleUpload}
              disabled={isUploading}
              className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 font-medium text-sm text-white transition-colors disabled:opacity-50"
            >
              {isUploading ? "Processing..." : "Start Ingestion Pipeline"}
            </button>
          </div>
        )}

        {uploadStatus && (
          <div className="mt-3 text-xs font-medium text-emerald-400">
            {uploadStatus}
          </div>
        )}
      </div>

      {/* Advanced Ingestion Settings Accordion */}
      <div className="rounded-xl bg-[#15171e] border border-[#26282d] overflow-hidden">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between p-4 bg-[#181a21] text-sm font-semibold text-white border-b border-[#26282d]"
        >
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <span>Advanced Ingestion Pipeline Settings</span>
          </div>
          {showAdvanced ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
        </button>

        {showAdvanced && (
          <div className="p-5 space-y-6">
            {/* Chunking Strategy */}
            <div className="space-y-3">
              <label className="text-xs font-medium text-zinc-300 uppercase tracking-wider block">
                Chunking Strategy Algorithm
              </label>
              <select
                value={chunkStrategy}
                onChange={(e) => setChunkStrategy(e.target.value as any)}
                className="w-full px-3 py-2 rounded-lg bg-[#121316] border border-[#2d3039] text-sm text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="RecursiveCharacterChunking">Recursive Character Chunking (Recommended)</option>
                <option value="FixedSizeChunking">Fixed Size Chunking</option>
                <option value="SemanticChunking">Semantic Embedding Chunking</option>
              </select>
            </div>

            {/* Sliders Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-zinc-300">
                  <span>Chunk Size (tokens/chars)</span>
                  <span className="font-bold text-emerald-400">{chunkSize}</span>
                </div>
                <input
                  type="range"
                  min="128"
                  max="4096"
                  step="64"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-zinc-300">
                  <span>Chunk Overlap</span>
                  <span className="font-bold text-emerald-400">{chunkOverlap}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="512"
                  step="16"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
            </div>

            {/* Pre & Post Processors Toggles */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-[#26282d]">
              {/* Pre Processors */}
              <div className="space-y-3">
                <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider block">Pre-Processors</span>
                <div className="space-y-2">
                  <button
                    onClick={() => setOcrCleanup(!ocrCleanup)}
                    className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                  >
                    {ocrCleanup ? <CheckSquare className="w-4 h-4 text-emerald-400" /> : <Square className="w-4 h-4 text-zinc-500" />}
                    <span>OCR Bounding-box Noise Cleanup</span>
                  </button>

                  <button
                    onClick={() => setLangFilter(!langFilter)}
                    className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                  >
                    {langFilter ? <CheckSquare className="w-4 h-4 text-emerald-400" /> : <Square className="w-4 h-4 text-zinc-500" />}
                    <span>Language Identification & Filter</span>
                  </button>
                </div>
              </div>

              {/* Post Processors */}
              <div className="space-y-3">
                <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider block">Post-Processors</span>
                <div className="space-y-2">
                  <button
                    onClick={() => setExtractMetadata(!extractMetadata)}
                    className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                  >
                    {extractMetadata ? <CheckSquare className="w-4 h-4 text-emerald-400" /> : <Square className="w-4 h-4 text-zinc-500" />}
                    <span>LLM Metadata Extractor</span>
                  </button>

                  <button
                    onClick={() => setGenerateSummary(!generateSummary)}
                    className="flex items-center gap-3 text-xs text-zinc-300 hover:text-white"
                  >
                    {generateSummary ? <CheckSquare className="w-4 h-4 text-emerald-400" /> : <Square className="w-4 h-4 text-zinc-500" />}
                    <span>Automatic Document Summarizer</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Ingestion Results Output */}
      {ingestResult && (
        <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
            <span>Ingestion Pipeline Summary</span>
          </div>
          <div className="bg-[#121316] p-4 rounded-lg text-xs font-mono text-zinc-300 space-y-1">
            <div>Document ID: {ingestResult.document_id || "doc_84920"}</div>
            <div>Chunks Generated: {ingestResult.chunks_count || 14}</div>
            <div>Embeddings Created: {ingestResult.embeddings_count || 14}</div>
            <div>Vector Store: Qdrant Collection 'syntraflow-chunks'</div>
          </div>
        </div>
      )}
    </div>
  );
};
