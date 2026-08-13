import { useState, useMemo } from "react";
import {
  Upload,
  X,
  Sliders,
  Sparkles,
  FileText,
  Video,
  Music,
  FileCode,
  Layers,
  ChevronDown,
  ChevronUp,
  Cpu,
  Database,
  Network,
  AlignLeft,
} from "lucide-react";
import { api } from "../../../services/api";

interface IngestionUploadModalProps {
  hubId: string;
  collections: any[];
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function IngestionUploadModal({
  hubId,
  collections,
  isOpen,
  onClose,
  onSuccess,
}: IngestionUploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [collectionId, setCollectionId] = useState<string>(
    collections[0]?.id || ""
  );

  // Accordion state
  const [showAdvanced, setShowAdvanced] = useState<boolean>(true);

  // Pipeline Engine Choices
  const [ocrEngine, setOcrEngine] = useState<string>("glm-ocr");
  const [chunkStrategy, setChunkStrategy] = useState<string>("layout-aware");
  const [chunkSize, setChunkSize] = useState<number>(512);
  const [chunkOverlap, setChunkOverlap] = useState<number>(64);
  const [embeddingModel, setEmbeddingModel] = useState<string>("jina-clip-v2");
  const [asrModel, setAsrModel] = useState<string>("sensevoice-small");
  const [ssimThreshold, setSsimThreshold] = useState<number>(0.3);

  // Post Processors
  const [enableSummary, setEnableSummary] = useState<boolean>(false);
  const [summaryModel, setSummaryModel] = useState<string>("gemini/gemini-2.5-flash");
  const [enableKeyphrase, setEnableKeyphrase] = useState<boolean>(true);
  const [enableTablePreserve, setEnableTablePreserve] = useState<boolean>(true);
  const [enableKG, setEnableKG] = useState<boolean>(false);
  const [graphModel, setGraphModel] = useState<string>("gemini/gemini-2.5-flash");

  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Detect category based on file extension
  const fileCategory = useMemo(() => {
    if (!selectedFile) return "document";
    const ext = selectedFile.name.split(".").pop()?.toLowerCase() || "";
    if (["mp4", "mov", "webm", "mkv", "wav", "mp3", "flac", "ogg"].includes(ext)) {
      return "media";
    }
    if (["txt", "md", "json", "csv", "log"].includes(ext)) {
      return "text";
    }
    return "document";
  }, [selectedFile]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hubId || !selectedFile || !collectionId) {
      setError("Please select a target collection and file.");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const postProcs: string[] = [];
      if (enableSummary) postProcs.push("summary_gen");
      if (enableKeyphrase) postProcs.push("keyphrase_extract");
      if (enableTablePreserve) postProcs.push("table_preserve");
      if (enableKG) postProcs.push("kg_extract");

      const pipelineCfg = {
        ocr_engine: fileCategory === "document" ? ocrEngine : "direct",
        chunking_strategy: chunkStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        embedding_model: embeddingModel,
        asr_model: fileCategory === "media" ? asrModel : undefined,
        ssim_threshold: fileCategory === "media" ? ssimThreshold : undefined,
        summary_model: enableSummary ? summaryModel : undefined,
        graph_model: enableKG ? graphModel : undefined,
        post_processors: postProcs,
      };

      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("collection_id", collectionId);
      formData.append("ocr_engine", pipelineCfg.ocr_engine);
      formData.append("chunk_strategy", chunkStrategy);
      formData.append("chunk_size", chunkSize.toString());
      formData.append("chunk_overlap", chunkOverlap.toString());
      formData.append("embedding_model", embeddingModel);
      if (summaryModel) formData.append("summary_model", summaryModel);
      if (graphModel) formData.append("graph_model", graphModel);
      formData.append("post_processors_json", JSON.stringify(postProcs));
      formData.append("pipeline_config_json", JSON.stringify(pipelineCfg));

      await api.ingestion.documents.ingest(hubId, formData);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.message || "Ingestion submission failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden text-slate-100 my-8">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100">
                Configurable Document Ingestion
              </h2>
              <p className="text-xs text-slate-400">
                Select document type, execution engines & post-processor enrichments
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="p-3.5 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Collection Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Target Collection <span className="text-red-400">*</span>
            </label>
            <select
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              required
              className="w-full bg-slate-850 border border-slate-750 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="" disabled>
                -- Select Target Collection --
              </option>
              {collections.map((col) => (
                <option key={col.id} value={col.id}>
                  {col.name} ({col.embedding_model || "jina-clip-v2"})
                </option>
              ))}
            </select>
          </div>

          {/* File Dropzone */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Upload File <span className="text-red-400">*</span>
            </label>
            <div className="relative border-2 border-dashed border-slate-750 hover:border-indigo-500/50 rounded-2xl p-6 text-center transition-colors bg-slate-950/40">
              <input
                type="file"
                required
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              {selectedFile ? (
                <div className="flex items-center justify-center space-x-3 text-indigo-400">
                  {fileCategory === "media" ? (
                    <Video className="w-8 h-8" />
                  ) : fileCategory === "text" ? (
                    <FileCode className="w-8 h-8" />
                  ) : (
                    <FileText className="w-8 h-8" />
                  )}
                  <div className="text-left">
                    <p className="text-sm font-semibold text-slate-100">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-slate-400">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB •{" "}
                      <span className="text-indigo-400 capitalize">
                        {fileCategory} Category
                      </span>
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="mx-auto w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400">
                    <Upload className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-medium text-slate-300">
                    Drag & drop file here or click to browse
                  </p>
                  <p className="text-xs text-slate-500">
                    Supports PDF, DOCX, PPTX, MP4, WAV, PNG, JPG, MD, JSON
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Advanced Pipeline Accordion */}
          <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/30">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-4 py-3 bg-slate-850/60 flex items-center justify-between text-xs font-semibold text-slate-300 uppercase tracking-wider hover:bg-slate-800 transition-colors"
            >
              <div className="flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                <span>Advanced Pipeline Configuration</span>
              </div>
              {showAdvanced ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {showAdvanced && (
              <div className="p-4 space-y-5 text-xs text-slate-300">
                {/* 1. OCR / Parsing Stage (for Documents) */}
                {fileCategory === "document" && (
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2 font-medium text-slate-200">
                      <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                      <span>OCR / Layout Extraction Engine</span>
                    </label>
                    <select
                      value={ocrEngine}
                      onChange={(e) => setOcrEngine(e.target.value)}
                      className="w-full bg-slate-850 border border-slate-750 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="direct">Direct Text Parser (Fastest, Plain Text/Clean PDF)</option>
                      <option value="glm-ocr">Local GLM-OCR (Layout & Formula Parsing)</option>
                      <option value="baidu-ocr">Baidu OCR (Tabular & Form Extraction)</option>
                      <option value="gemini-vlm">Gemini VLM (Cloud Multimodal Layout Conversion)</option>
                    </select>
                  </div>
                )}

                {/* 1b. ASR / Media Sampling Stage (for Audio/Video) */}
                {fileCategory === "media" && (
                  <div className="space-y-4 border-b border-slate-800/80 pb-4">
                    <div className="space-y-2">
                      <label className="flex items-center space-x-2 font-medium text-slate-200">
                        <Music className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Speech-to-Text Model (ASR)</span>
                      </label>
                      <select
                        value={asrModel}
                        onChange={(e) => setAsrModel(e.target.value)}
                        className="w-full bg-slate-850 border border-slate-750 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                      >
                        <option value="sensevoice-small">SenseVoice-Small (Fast, Timestamp & Emotion Markers)</option>
                        <option value="whisper-base">Whisper Base (Multilingual)</option>
                        <option value="whisper-large">Whisper Large v3 (High Precision)</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="font-medium text-slate-200">
                          SSIM Keyframe Sampling Sensitivity
                        </span>
                        <span className="text-indigo-400 font-mono">
                          {ssimThreshold}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={ssimThreshold}
                        onChange={(e) => setSsimThreshold(parseFloat(e.target.value))}
                        className="w-full accent-indigo-500"
                      />
                    </div>
                  </div>
                )}

                {/* 2. Chunking Strategy & Sliders */}
                <div className="space-y-3 pt-1 border-t border-slate-800/80">
                  <label className="flex items-center space-x-2 font-medium text-slate-200">
                    <AlignLeft className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Chunking Strategy</span>
                  </label>
                  <select
                    value={chunkStrategy}
                    onChange={(e) => setChunkStrategy(e.target.value)}
                    className="w-full bg-slate-850 border border-slate-750 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="layout-aware">Layout-Aware Section Hierarchy Chunking</option>
                    <option value="recursive">Recursive Character Chunking</option>
                    <option value="semantic">Semantic Sentence Boundary Chunking</option>
                  </select>

                  <div className="grid grid-cols-2 gap-4 pt-2">
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Chunk Size</span>
                        <span className="text-indigo-400 font-mono">{chunkSize} tokens</span>
                      </div>
                      <input
                        type="range"
                        min="128"
                        max="2048"
                        step="64"
                        value={chunkSize}
                        onChange={(e) => setChunkSize(parseInt(e.target.value))}
                        className="w-full accent-indigo-500"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Chunk Overlap</span>
                        <span className="text-indigo-400 font-mono">{chunkOverlap} tokens</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="256"
                        step="16"
                        value={chunkOverlap}
                        onChange={(e) => setChunkOverlap(parseInt(e.target.value))}
                        className="w-full accent-indigo-500"
                      />
                    </div>
                  </div>
                </div>

                {/* 3. Embedding Model */}
                <div className="space-y-2 pt-2 border-t border-slate-800/80">
                  <label className="flex items-center space-x-2 font-medium text-slate-200">
                    <Database className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Vector Embedding Model</span>
                  </label>
                  <select
                    value={embeddingModel}
                    onChange={(e) => setEmbeddingModel(e.target.value)}
                    className="w-full bg-slate-850 border border-slate-750 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="jina-clip-v2">Jina CLIP v2 (1024d Multimodal)</option>
                    <option value="harrier-0.6b">Harrier 0.6B (768d Local CPU/GPU)</option>
                    <option value="harrier-270m">Harrier 270M (768d Local CPU/GPU)</option>
                    <option value="BAAI/bge-base-en-v1.5">BGE Base English v1.5 (768d)</option>
                    <option value="nomic-embed-vision-v1.5">Nomic Embed Vision v1.5 (768d)</option>
                  </select>
                </div>

                {/* 4. Multi-Selectable Post Processors */}
                <div className="space-y-3 pt-3 border-t border-slate-800/80">
                  <label className="flex items-center space-x-2 font-medium text-slate-200">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Post-Processing Enrichments</span>
                  </label>

                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex items-center space-x-2.5 p-2.5 rounded-lg bg-slate-850 border border-slate-750 cursor-pointer hover:border-slate-650 transition-colors">
                      <input
                        type="checkbox"
                        checked={enableKeyphrase}
                        onChange={(e) => setEnableKeyphrase(e.target.checked)}
                        className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 accent-indigo-500"
                      />
                      <span className="text-slate-300 font-medium">Keyphrase Extraction</span>
                    </label>

                    <label className="flex items-center space-x-2.5 p-2.5 rounded-lg bg-slate-850 border border-slate-750 cursor-pointer hover:border-slate-650 transition-colors">
                      <input
                        type="checkbox"
                        checked={enableTablePreserve}
                        onChange={(e) => setEnableTablePreserve(e.target.checked)}
                        className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 accent-indigo-500"
                      />
                      <span className="text-slate-300 font-medium">Table Structure Preservation</span>
                    </label>
                  </div>

                  {/* Summary Gen */}
                  <div className="p-3 rounded-xl bg-slate-850 border border-slate-750 space-y-2">
                    <label className="flex items-center justify-between cursor-pointer">
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={enableSummary}
                          onChange={(e) => setEnableSummary(e.target.checked)}
                          className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 accent-indigo-500"
                        />
                        <span className="text-slate-200 font-medium">Document Summary Generation</span>
                      </div>
                    </label>
                    {enableSummary && (
                      <div className="pt-2">
                        <label className="block text-[11px] text-slate-400 mb-1">
                          LLM Summary Model
                        </label>
                        <select
                          value={summaryModel}
                          onChange={(e) => setSummaryModel(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-750 rounded-md px-2.5 py-1.5 text-xs text-slate-200"
                        >
                          <option value="gemini/gemini-2.5-flash">Gemini 2.5 Flash</option>
                          <option value="ollama/llama3">Ollama Llama 3</option>
                          <option value="gpt-4o">OpenAI GPT-4o</option>
                        </select>
                      </div>
                    )}
                  </div>

                  {/* Knowledge Graph Extraction */}
                  <div className="p-3 rounded-xl bg-slate-850 border border-slate-750 space-y-2">
                    <label className="flex items-center justify-between cursor-pointer">
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={enableKG}
                          onChange={(e) => setEnableKG(e.target.checked)}
                          className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 accent-indigo-500"
                        />
                        <div className="flex items-center space-x-1.5">
                          <Network className="w-3.5 h-3.5 text-indigo-400" />
                          <span className="text-slate-200 font-medium">
                            Knowledge Graph Extraction (Neo4j)
                          </span>
                        </div>
                      </div>
                    </label>
                    {enableKG && (
                      <div className="pt-2">
                        <label className="block text-[11px] text-slate-400 mb-1">
                          Entity Extractor LLM Model
                        </label>
                        <select
                          value={graphModel}
                          onChange={(e) => setGraphModel(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-750 rounded-md px-2.5 py-1.5 text-xs text-slate-200"
                        >
                          <option value="gemini/gemini-2.5-flash">Gemini 2.5 Flash</option>
                          <option value="ollama/llama3">Ollama Llama 3</option>
                        </select>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading || !selectedFile || !collectionId}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all flex items-center space-x-2"
            >
              {uploading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Submitting Ingestion Job...</span>
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  <span>Start Configured Ingestion</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
