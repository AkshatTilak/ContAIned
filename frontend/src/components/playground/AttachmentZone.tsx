import React, { useRef, useState } from "react";
import { Paperclip, X, FileText, Image, Film, Loader2, Eye, ChevronDown, ChevronUp } from "lucide-react";
import type { PlaygroundAttachment } from "../../types/api";

interface AttachmentZoneProps {
  attachments: PlaygroundAttachment[];
  onUploadFile: (file: File) => Promise<void>;
  onRemoveAttachment: (id: string) => void;
  isUploading: boolean;
}

export const AttachmentZone: React.FC<AttachmentZoneProps> = ({
  attachments,
  onUploadFile,
  onRemoveAttachment,
  isUploading,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      for (let i = 0; i < files.length; i++) {
        await onUploadFile(files[i]);
      }
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        await onUploadFile(e.dataTransfer.files[i]);
      }
    }
  };

  const getFileIcon = (fileType: string) => {
    const ft = fileType.toLowerCase();
    if (["png", "jpg", "jpeg", "webp"].includes(ft)) return Image;
    if (["mp4", "webm"].includes(ft)) return Film;
    return FileText;
  };

  return (
    <div className="w-full space-y-2">
      {/* Upload Drop Zone / Button Bar */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`flex items-center gap-2 p-2 rounded-xl border border-dashed transition-all ${
          isDragOver
            ? "border-emerald-500 bg-emerald-500/10"
            : "border-[var(--border-subtle)] hover:border-zinc-500 bg-[var(--bg-surface-alt)]/50"
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.webp,.mp4,.webm,.txt,.md,.csv"
          multiple
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[var(--border-subtle)] text-xs font-medium text-zinc-300 transition-colors disabled:opacity-50"
        >
          {isUploading ? (
            <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
          ) : (
            <Paperclip className="w-3.5 h-3.5 text-emerald-400" />
          )}
          <span>Attach Files (PDF, Image, Video, TXT)</span>
        </button>
        <span className="text-[11px] text-zinc-500 hidden sm:inline">
          Drag & drop files here to extract context
        </span>
      </div>

      {/* Attachment Chips */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {attachments.map((att) => {
            const Icon = getFileIcon(att.file_type);
            const isExpanded = expandedId === att.attachment_id;
            return (
              <div
                key={att.attachment_id}
                className="flex flex-col bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-xl px-3 py-1.5 text-xs text-zinc-200 transition-all max-w-full"
              >
                <div className="flex items-center gap-2">
                  <Icon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="font-mono truncate max-w-[180px]" title={att.filename}>
                    {att.filename}
                  </span>
                  <span className="text-[10px] uppercase font-bold text-zinc-500 px-1.5 py-0.5 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)]">
                    {att.file_type}
                  </span>
                  {att.extracted_text_preview && (
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : att.attachment_id)}
                      className="p-1 hover:text-emerald-400 text-zinc-400 transition-colors"
                      title={isExpanded ? "Hide Preview" : "View Extracted Text"}
                    >
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onRemoveAttachment(att.attachment_id)}
                    className="p-1 text-zinc-500 hover:text-rose-400 transition-colors ml-auto"
                    title="Remove Attachment"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Expanded Extracted Text Drawer */}
                {isExpanded && att.extracted_text_preview && (
                  <div className="mt-2 p-2 rounded-lg bg-[#0d0e12] border border-[var(--border-subtle)] text-[11px] font-mono text-zinc-300 max-h-32 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
                    {att.extracted_text_preview}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
