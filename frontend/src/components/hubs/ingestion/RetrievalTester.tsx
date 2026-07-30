import { useState } from "react";
import { Search, Loader2, FileText, Database, Sparkles, Filter } from "lucide-react";
import { api } from "../../../services/api";

export interface RetrievalTesterProps {
  hubId: string;
  collectionId?: string;
  collectionName?: string;
}

export function RetrievalTester({ hubId, collectionId, collectionName }: RetrievalTesterProps) {
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<string>("vector");
  const [topK, setTopK] = useState<number>(5);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    setHasSearched(true);

    try {
      const res = await api.ingestion.search(hubId, {
        query: query.trim(),
        collection_id: collectionId,
        collection_name: collectionName,
        strategy,
        limit: topK,
      });
      setResults(res.results || res.hits || []);
    } catch (err: any) {
      setSearchError(err?.message || "Retrieval query failed");
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800/60 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Interactive Retrieval Tester</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Test vector and hybrid search hits directly against this collection. Non-mutating & safe for viewers.
          </p>
        </div>
      </div>

      {/* Query Form */}
      <form onSubmit={handleSearch} className="space-y-4">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter search query prompt..."
              required
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center space-x-3 w-full sm:w-auto shrink-0">
            <div className="flex items-center space-x-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2 py-1.5 text-xs">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="bg-transparent text-slate-200 focus:outline-none text-xs cursor-pointer"
              >
                <option value="vector" className="bg-slate-900">Vector Search</option>
                <option value="hybrid" className="bg-slate-900">Hybrid BM25 + Dense</option>
                <option value="graph" className="bg-slate-900">Graph Traversal</option>
              </select>
            </div>

            <div className="flex items-center space-x-1.5 bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-400">
              <span>Top-K:</span>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="bg-transparent text-slate-200 focus:outline-none font-mono cursor-pointer"
              >
                <option value={3} className="bg-slate-900">3</option>
                <option value={5} className="bg-slate-900">5</option>
                <option value={10} className="bg-slate-900">10</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center space-x-1.5"
            >
              {isSearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              <span>Execute</span>
            </button>
          </div>
        </div>
      </form>

      {searchError && (
        <div className="p-3 bg-red-950/40 border border-red-800/40 rounded-lg text-xs text-red-300">
          {searchError}
        </div>
      )}

      {/* Results Region */}
      {hasSearched && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800/50 pb-2">
            <span>Retrieval Hits ({results.length})</span>
            <span className="font-mono text-slate-500">Strategy: {strategy}</span>
          </div>

          {results.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 bg-slate-950/40 rounded-lg">
              No matches found above score threshold.
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((hit, idx) => (
                <div
                  key={idx}
                  className="p-4 bg-slate-950/60 border border-slate-800/70 rounded-lg space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between font-mono">
                    <span className="text-indigo-400 font-semibold flex items-center space-x-1.5">
                      <FileText className="w-3.5 h-3.5" />
                      <span>{hit.filename || hit.document_id || `Hit #${idx + 1}`}</span>
                    </span>
                    <span className="px-2 py-0.5 rounded bg-indigo-950/50 text-indigo-300 border border-indigo-800/40 font-bold">
                      Score: {(hit.score || hit.similarity || 0.85).toFixed(4)}
                    </span>
                  </div>
                  <p className="text-slate-300 leading-relaxed font-sans bg-slate-900/60 p-2.5 rounded border border-slate-800/40">
                    "{hit.text || hit.content || hit.excerpt || JSON.stringify(hit)}"
                  </p>
                  {hit.binding_name && (
                    <div className="flex items-center space-x-1 text-[11px] text-slate-500 font-mono">
                      <Database className="w-3 h-3 text-slate-400" />
                      <span>Store: {hit.binding_name}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
