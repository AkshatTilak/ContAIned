import React, { useState, useEffect } from "react";
import { Code, Terminal, Copy, Check, Box } from "lucide-react";

interface ModelItem {
  id: string;
  owned_by: string;
}

export const APIDocsPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"python" | "curl" | "js">("python");
  const [copiedTab, setCopiedTab] = useState<boolean>(false);
  const [models, setModels] = useState<ModelItem[]>([]);

  useEffect(() => {
    fetch("/v1/models")
      .then((res) => (res.ok ? res.json() : { data: [] }))
      .then((data) => setModels(data.data || []))
      .catch(() => setModels([]));
  }, []);

  const pythonCode = `from openai import OpenAI

# Initialize OpenAI client targeting ContAIned API Gateway
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-your-api-key-here"
)

# 1. Direct LLM completion
response = client.chat.completions.create(
    model="gemini/gemini-3.5-flash",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain vector embeddings simply."}
    ]
)
print(response.choices[0].message.content)

# 2. Invoke an agent by its endpoint slug
agent_response = client.chat.completions.create(
    model="my-research-agent",  # Agent endpoint_slug
    messages=[{"role": "user", "content": "Search latest papers on transformers"}]
)
print(agent_response.choices[0].message.content)`;

  const curlCode = `# 1. List available models & agent slugs
curl http://localhost:8000/v1/models \\
  -H "Authorization: Bearer sk-your-api-key-here"

# 2. OpenAI-compatible Chat Completion
curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-your-api-key-here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gemini/gemini-3.5-flash",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7
  }'`;

  const jsCode = `import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "sk-your-api-key-here",
});

async function main() {
  const completion = await openai.chat.completions.create({
    messages: [{ role: "user", content: "Hello world!" }],
    model: "gemini/gemini-3.5-flash",
  });

  console.log(completion.choices[0].message.content);
}
main();`;

  const currentCode = activeTab === "python" ? pythonCode : activeTab === "curl" ? curlCode : jsCode;

  const copyCode = () => {
    navigator.clipboard.writeText(currentCode);
    setCopiedTab(true);
    setTimeout(() => setCopiedTab(false), 2000);
  };

  return (
    <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 space-y-6 shadow-sm">
      <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] pb-4">
        <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
          <Terminal className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-base font-bold font-display text-[var(--text-primary)]">
            External API Gateway Documentation
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            Connect any OpenAI SDK client directly to ContAIned's models and agents.
          </p>
        </div>
      </div>

      {/* Code Snippets Box */}
      <div className="bg-[var(--bg-input)] border border-[var(--border-default)] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-surface-alt)] border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("python")}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                activeTab === "python"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              Python (openai SDK)
            </button>
            <button
              onClick={() => setActiveTab("curl")}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                activeTab === "curl"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              cURL
            </button>
            <button
              onClick={() => setActiveTab("js")}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                activeTab === "js"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              JavaScript / Node.js
            </button>
          </div>
          <button
            onClick={copyCode}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[var(--bg-elevated)] hover:bg-[var(--bg-input)] text-xs text-zinc-300 transition-all border border-[var(--border-default)]"
          >
            {copiedTab ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedTab ? "Copied!" : "Copy Snippet"}</span>
          </button>
        </div>
        <pre className="p-4 text-xs font-mono text-zinc-300 overflow-x-auto leading-relaxed">
          <code>{currentCode}</code>
        </pre>
      </div>

      {/* Available Models List */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs font-bold font-display text-[var(--text-primary)]">
          <Box className="w-4 h-4 text-emerald-400" />
          <span>Available Models & Agent Slugs (`GET /v1/models`)</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {models.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] italic">No active models or agents found.</p>
          ) : (
            models.map((m, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] flex items-center justify-between text-xs font-mono"
              >
                <span className="text-emerald-400 font-semibold truncate max-w-[180px]">{m.id}</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                  {m.owned_by}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
