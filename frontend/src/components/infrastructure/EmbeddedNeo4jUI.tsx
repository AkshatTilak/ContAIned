import React, { useState } from "react";
import { Share2, RefreshCw, ExternalLink, Maximize2, Minimize2, Network } from "lucide-react";
import { useStore } from "../../store/useStore";

export const EmbeddedNeo4jUI: React.FC = () => {
  const gatewayUrl = useStore((state) => state.gatewayUrl) || "http://localhost:8000";
  const [iframeKey, setIframeKey] = useState<number>(0);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const proxyUrl = `${gatewayUrl.replace(/\/$/, "")}/api/neo4j/browser/`;
  const directUrl = "http://localhost:7474/browser/";

  const handleReload = () => {
    setIsLoading(true);
    setIframeKey((prev) => prev + 1);
  };

  return (
    <div className={`flex flex-col gap-4 ${isFullscreen ? "fixed inset-0 z-50 bg-[#09090b] p-6" : "w-full"}`}>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-gray-900/60 border border-gray-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Share2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-gray-100">Neo4j Graph Browser</h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Gateway Proxied
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">Execute Cypher queries and inspect knowledge graph entity relationships</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleReload}
            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors text-xs flex items-center gap-1.5 border border-gray-700"
            title="Reload Iframe"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Reload</span>
          </button>

          <a
            href={directUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors text-xs flex items-center gap-1.5 border border-gray-700"
            title="Open in new tab"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>Open Direct</span>
          </a>

          <button
            onClick={() => setIsFullscreen((prev) => !prev)}
            className="p-2 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 transition-colors text-xs flex items-center gap-1.5 border border-purple-500/30"
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            <span>{isFullscreen ? "Exit Fullscreen" : "Fullscreen"}</span>
          </button>
        </div>
      </div>

      {/* Connection Info Banner */}
      <div className="px-4 py-2.5 rounded-xl bg-purple-500/5 border border-purple-500/20 text-xs flex flex-wrap items-center justify-between gap-2 text-purple-300">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-purple-400 shrink-0" />
          <span><strong>Neo4j Connect Settings:</strong> Connect URL: <code className="px-1.5 py-0.5 rounded bg-gray-900 font-mono text-purple-200">bolt://localhost:7687</code></span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-gray-400">
          <span>Username: <strong className="text-gray-200">neo4j</strong></span>
          <span>Password: <strong className="text-gray-200">changeme</strong> (or <code className="text-purple-300">NEO4J_PASSWORD</code> from .env)</span>
        </div>
      </div>

      {/* Embedded Iframe Container */}
      <div className="relative w-full rounded-xl overflow-hidden border border-gray-800 bg-gray-950 flex-1 min-h-[600px] shadow-2xl">
        {isLoading && (
          <div className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm flex items-center justify-center z-10">
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <RefreshCw className="w-4 h-4 animate-spin text-purple-400" />
              <span>Loading Neo4j Browser via Reverse Proxy...</span>
            </div>
          </div>
        )}

        <iframe
          key={iframeKey}
          src={proxyUrl}
          title="Neo4j Graph Browser"
          onLoad={() => setIsLoading(false)}
          className="w-full h-full min-h-[650px] border-0"
        />
      </div>
    </div>
  );
};
