import React, { useState } from "react";
import { Search, Sliders, Play, Layers, Filter, Sparkles, AlertCircle, FileText } from "lucide-react";
import { api } from "../../services/api";

type StrategyType = "dense" | "sparse" | "hybrid" | "graph";

export const RetrievalTester: React.FC = () => {
  const [query, setQuery] = useState<string>("");
  const [collectionName, setCollectionName] = useState<string>("syntraflow_chunks_v1");
  const [strategy, setStrategy] = useState<StrategyType>("hybrid");
  const [limit, setLimit] = useState<number>(5);

  // Metadata filter key-value pairs
  const [tenantFilter, setTenantFilter] = useState<string>("");
  const [tagFilter, setTagFilter] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(false);
  const [results, setResults] = useState<any[]>([]);
  const [executedQueryInfo, setExecutedQueryInfo] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    const filters: Record<string, any> = {};
    if (tenantFilter.trim()) filters["tenant_id"] = tenantFilter.trim();
    if (tagFilter.trim()) filters["tags"] = tagFilter.trim().split(",").map((t) => t.trim());

    try {
      const res = await api.queryRetrievalEngine({
        query: query.trim(),
        collection_name: collectionName.trim() || "syntraflow_chunks_v1",
        strategy: strategy,
        limit: Number(limit),
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      });

      setResults(res.results || []);
      setExecutedQueryInfo({
        query: res.query,
        strategy: res.strategy,
        count: res.count,
      });
    } catch (err: any) {
      setError(err.message || "Retrieval engine query failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            Pluggable Retrieval Strategy Tester
          </h3>
          <p className="text-sm text-slate-400">
            Test Vector Cosine Similarity (Dense), BM25 Keyword (Sparse), RRF Fusion (Hybrid), and Neo4j Graph traversal.
          </p>
        </div>

        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="text"
                required
                placeholder="Enter natural language query or concept..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-600/20"
            >
              <Play className="w-4 h-4" />
              <span>{loading ? "Searching..." : "Execute Search"}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Strategy</label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as StrategyType)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 capitalize"
              >
                <option value="dense">Dense (Vector Cosine)</option>
                <option value="sparse">Sparse (BM25 Keyword)</option>
                <option value="hybrid">Hybrid (RRF Fusion)</option>
                <option value="graph">Graph (Neo4j Entity)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Collection</label>
              <input
                type="text"
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Tenant Filter</label>
              <input
                type="text"
                placeholder="e.g. default"
                value={tenantFilter}
                onChange={(e) => setTenantFilter(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Max Hits</label>
              <input
                type="number"
                min={1}
                max={20}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>
        </form>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/50 text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Results */}
      {executedQueryInfo && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span>
              Results for <strong className="text-slate-200 font-mono">"{executedQueryInfo.query}"</strong> using{" "}
              <strong className="text-indigo-400 uppercase font-mono">{executedQueryInfo.strategy}</strong> strategy
            </span>
            <span className="font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-300">
              {results.length} hits returned
            </span>
          </div>

          {results.length === 0 ? (
            <div className="text-center p-8 bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400 text-sm">
              No matching records found for this query strategy or filter condition.
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((hit, idx) => (
                <div
                  key={hit.id || idx}
                  className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 space-y-2 hover:border-slate-700 transition-all"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-indigo-400 font-semibold">#{idx + 1}</span>
                      <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono uppercase text-[10px]">
                        {hit.strategy || strategy}
                      </span>
                    </div>
                    <span className="font-mono text-slate-400">
                      Score: <strong className="text-emerald-400">{typeof hit.score === "number" ? hit.score.toFixed(4) : hit.score}</strong>
                    </span>
                  </div>

                  <p className="text-sm text-slate-200 leading-relaxed font-sans bg-slate-950/50 p-3 rounded-lg border border-slate-800/50">
                    {hit.text}
                  </p>

                  {hit.metadata && Object.keys(hit.metadata).length > 0 && (
                    <details className="text-xs text-slate-500">
                      <summary className="cursor-pointer hover:text-slate-400 font-mono text-[11px]">
                        Payload Metadata
                      </summary>
                      <pre className="mt-2 bg-slate-950 p-2 rounded border border-slate-800/80 text-[10px] text-slate-400 font-mono overflow-x-auto">
                        {JSON.stringify(hit.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
