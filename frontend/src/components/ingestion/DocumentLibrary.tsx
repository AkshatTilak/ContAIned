import React, { useEffect, useState, useCallback } from "react";
import {
  FileText,
  Search,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  X,
  Layers,
  Hash,
} from "lucide-react";
import { api } from "../../services/api";
import { LoadingSkeleton } from "../shared/LoadingSkeleton";
import { ErrorBanner } from "../shared/ErrorBanner";
import { ConfirmModal } from "../shared/ConfirmModal";
import type { SyntraFlowDocument, DocumentChunk } from "../../types/api";

export const DocumentLibrary: React.FC = () => {
  const [documents, setDocuments] = useState<SyntraFlowDocument[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Pagination State
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // View Chunks Modal State
  const [selectedDoc, setSelectedDoc] = useState<SyntraFlowDocument | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  // Delete Confirmation Modal State
  const [deletingDoc, setDeletingDoc] = useState<SyntraFlowDocument | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const offset = page * pageSize;
      const res = await api.getDocuments(pageSize, offset);
      setDocuments(res.items || []);
      setTotalCount(res.total_count || 0);
    } catch (err: any) {
      setError(err?.message || "Failed to fetch document library");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Filtered documents by search query
  const filteredDocs = documents.filter((doc) =>
    (doc.filename || doc.id || "")
      .toLowerCase()
      .includes(searchQuery.toLowerCase())
  );

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  // Handle View Chunks
  const handleViewChunks = async (doc: SyntraFlowDocument) => {
    setSelectedDoc(doc);
    setChunksLoading(true);
    try {
      const res = await api.getDocumentChunks(doc.id, 20, 0);
      setChunks(res.items || []);
    } catch (err) {
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  // Handle Delete Document
  const handleDeleteConfirm = async () => {
    if (!deletingDoc) return;
    try {
      await api.deleteDocument(deletingDoc.id);
      setDeletingDoc(null);
      fetchDocuments();
    } catch (err: any) {
      setError(err?.message || "Failed to delete document");
    }
  };

  return (
    <div className="p-6 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-default)] space-y-4">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-default)] pb-4">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-emerald-400" />
            Ingested Document Library
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Browse, inspect chunks, and manage knowledge base documents across Qdrant vector store.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 w-48 sm:w-64"
            />
          </div>

          <button
            onClick={fetchDocuments}
            className="p-2 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] text-zinc-300 hover:text-white border border-[var(--border-default)] transition-colors text-xs flex items-center gap-1.5"
            title="Refresh List"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchDocuments} />}

      {loading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : filteredDocs.length === 0 ? (
        <div className="py-12 text-center text-zinc-500 text-xs">
          {searchQuery ? "No matching documents found." : "No documents ingested yet."}
        </div>
      ) : (
        <>
          {/* Document Table */}
          <div className="overflow-x-auto rounded-2xl border border-[var(--border-default)] bg-[#0e0e12] shadow-2xl">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="bg-[#13141a] border-b border-[var(--border-default)] text-zinc-400 uppercase tracking-wider text-[10px] font-bold">
                <tr>
                  <th className="py-5 px-6">Document Name</th>
                  <th className="py-5 px-6">Type</th>
                  <th className="py-5 px-6">File Hash</th>
                  <th className="py-5 px-6">Ingested Date</th>
                  <th className="py-5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {filteredDocs.map((doc) => {
                  const docName = doc.filename || "Untitled Document";
                  const ext = doc.file_type || docName.split(".").pop()?.toUpperCase() || "FILE";
                  const hashShort = doc.file_hash ? doc.file_hash.slice(0, 10) : doc.id.slice(0, 10);

                  return (
                    <tr
                      key={doc.id}
                      className="hover:bg-zinc-800/30 transition-colors"
                    >
                      <td className="py-5 px-6 font-semibold text-white flex items-center gap-3">
                        <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="truncate max-w-sm">{docName}</span>
                      </td>
                      <td className="py-5 px-6">
                        <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 uppercase">
                          {ext}
                        </span>
                      </td>
                      <td className="py-5 px-6 font-mono text-zinc-400 text-xs">
                        <div className="flex items-center gap-1.5">
                          <Hash className="w-3.5 h-3.5 text-zinc-500" />
                          {hashShort}...
                        </div>
                      </td>
                      <td className="py-5 px-6 text-zinc-400 text-xs">
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "N/A"}
                      </td>
                      <td className="py-5 px-6 text-right">
                        <div className="flex items-center justify-end gap-2.5">
                          <button
                            onClick={() => handleViewChunks(doc)}
                            className="p-1.5 rounded bg-[var(--bg-input)] hover:bg-emerald-500/20 text-zinc-300 hover:text-emerald-400 transition-colors"
                            title="View Document Chunks"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeletingDoc(doc)}
                            className="p-1.5 rounded bg-[var(--bg-input)] hover:bg-red-500/20 text-zinc-300 hover:text-red-400 transition-colors"
                            title="Delete Document"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="flex items-center justify-between pt-4 border-t border-[var(--border-default)] text-xs text-zinc-400">
            <span>
              Showing Page {page + 1} of {totalPages} ({totalCount} total)
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="p-1.5 rounded bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] disabled:opacity-40 disabled:hover:bg-[var(--bg-input)] transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] disabled:opacity-40 disabled:hover:bg-[var(--bg-input)] transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}

      {/* View Chunks Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-[var(--border-default)] flex items-center justify-between bg-[var(--bg-surface-alt)]">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-emerald-400" />
                <h4 className="text-sm font-semibold text-white truncate max-w-md">
                  Document Chunks: {selectedDoc.filename}
                </h4>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1 rounded text-zinc-400 hover:text-white hover:bg-[var(--bg-hover)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {chunksLoading ? (
                <LoadingSkeleton variant="card" count={3} />
              ) : chunks.length === 0 ? (
                <div className="py-8 text-center text-zinc-500 text-xs">
                  No vector chunks found for this document.
                </div>
              ) : (
                chunks.map((chunk, idx) => (
                  <div
                    key={chunk.id || idx}
                    className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px] text-emerald-400 font-mono">
                      <span>Chunk #{chunk.chunk_index ?? idx + 1} ({chunk.token_count || 0} tokens)</span>
                      <span className="text-zinc-500 font-mono text-[10px]">
                        ID: {chunk.id?.slice(0, 12) || `chunk_${idx}`}
                      </span>
                    </div>
                    <p className="text-zinc-300 font-mono text-[11px] leading-relaxed bg-[var(--bg-surface)] p-2.5 rounded border border-[var(--border-default)] whitespace-pre-wrap">
                      {chunk.text || "No text content available"}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 border-t border-[var(--border-default)] bg-[var(--bg-surface-alt)] flex justify-end">
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-1.5 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] text-xs text-white font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Document Confirmation Modal */}
      {deletingDoc && (
        <ConfirmModal
          isOpen={true}
          title="Delete Document & Chunks"
          message={`Are you sure you want to permanently delete "${deletingDoc.filename}" and all associated vector embeddings from Qdrant?`}
          confirmLabel="Delete Document"
          cancelLabel="Cancel"
          isDanger={true}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeletingDoc(null)}
        />
      )}
    </div>
  );
};
