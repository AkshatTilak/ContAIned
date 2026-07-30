import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Layers,
  Bot,
  GitFork,
  CheckSquare,
  ArrowRight,
  ArrowLeft,
  Check,
  Building2,
  Sparkles,
  Shield,
  Link2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { routes, type HubType } from "../../routes";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";
import type { HubRole, HubAccessLevel, Hub } from "../../types/api";

const HUB_TYPES_INFO: {
  type: HubType;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}[] = [
  {
    type: "ingestion",
    title: "Ingestion Hub",
    description: "Hosts vector collection bindings, dynamic vector stores, and document ingestion pipelines.",
    icon: Layers,
    accent: "#10b981", // emerald
  },
  {
    type: "agent",
    title: "Agent Hub",
    description: "Hosts autonomous AI agents, system prompts, role definitions, and tool integrations.",
    icon: Bot,
    accent: "#6366f1", // indigo
  },
  {
    type: "workflow",
    title: "Workflow Hub",
    description: "Hosts multi-workflow graphs, visual execution nodes, and versioned graph releases.",
    icon: GitFork,
    accent: "#f59e0b", // amber
  },
  {
    type: "eval",
    title: "Eval Hub",
    description: "Hosts polymorphic test suites, RAGAS/DeepEval scoring, and node assertion tracing.",
    icon: CheckSquare,
    accent: "#06b6d4", // cyan
  },
];

const ACCENT_OPTIONS = ["#10b981", "#6366f1", "#f59e0b", "#06b6d4", "#ec4899", "#8b5cf6"];

// Legal link direction matrix from hubs.md §3.3
const LEGAL_LINK_TARGETS: Record<HubType, HubType[]> = {
  ingestion: [], // cannot link out
  agent: ["ingestion"],
  workflow: ["agent", "ingestion"],
  eval: ["workflow", "agent"],
};

export function HubCreateWizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const hubsById = useStore((state) => state.hubsById);
  const existingHubs = useMemo(() => Object.values(hubsById), [hubsById]);

  const initialType = (searchParams.get("type") as HubType) || "ingestion";

  const [step, setStep] = useState<number>(1);
  const [hubType, setHubType] = useState<HubType>(initialType);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [isSlugManual, setIsSlugManual] = useState(false);
  const [description, setDescription] = useState("");
  const [accent, setAccent] = useState(HUB_TYPES_INFO.find((t) => t.type === initialType)?.accent || "#6366f1");
  const [selectedLinks, setSelectedLinks] = useState<{ target_hub_id: string; access_level: HubAccessLevel }[]>([]);

  const [slugStatus, setSlugStatus] = useState<"idle" | "checking" | "available" | "taken" | "invalid">("idle");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Auto-derive slug from name
  useEffect(() => {
    if (!isSlugManual && name) {
      const derived = name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
      setSlug(derived);
    }
  }, [name, isSlugManual]);

  // Live slug uniqueness check
  useEffect(() => {
    if (!slug) {
      setSlugStatus("idle");
      return;
    }

    const isValid = /^[a-z0-9][a-z0-9-]{1,63}$/.test(slug);
    if (!isValid) {
      setSlugStatus("invalid");
      return;
    }

    setSlugStatus("checking");
    const timer = setTimeout(async () => {
      try {
        const res = await api.hubs.checkSlug(hubType, slug);
        setSlugStatus(res.available ? "available" : "taken");
      } catch {
        setSlugStatus("available");
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [slug, hubType]);

  const handleTypeSelect = (t: HubType) => {
    setHubType(t);
    const info = HUB_TYPES_INFO.find((item) => item.type === t);
    if (info) setAccent(info.accent);
    setSelectedLinks([]);
  };

  const legalTargetTypes = LEGAL_LINK_TARGETS[hubType] || [];
  const eligibleTargetHubs = useMemo(() => {
    return existingHubs.filter(
      (h) => legalTargetTypes.includes(h.hub_type) && !h.is_archived
    );
  }, [existingHubs, legalTargetTypes]);

  const toggleLink = (targetHubId: string) => {
    setSelectedLinks((prev) => {
      const exists = prev.find((l) => l.target_hub_id === targetHubId);
      if (exists) {
        return prev.filter((l) => l.target_hub_id !== targetHubId);
      }
      return [...prev, { target_hub_id: targetHubId, access_level: "use" }];
    });
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const newHub = await api.hubs.create({
        hub_type: hubType,
        name,
        slug,
        description,
        accent,
        initial_links: selectedLinks,
      });

      navigate(routes.hubs.shell(newHub.hub_type, newHub.id));
    } catch (err: any) {
      setSubmitError(err?.message || "Failed to create hub");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-12">
      {/* Wizard Header & Progress Bar */}
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-bold font-display text-slate-100 flex items-center justify-center space-x-3">
          <Sparkles className="w-6 h-6 text-indigo-400" />
          <span>Create New Hub</span>
        </h1>
        <p className="text-sm text-slate-400 max-w-md mx-auto">
          Step {step} of 4 — {step === 1 ? "Select Hub Type" : step === 2 ? "Identity & Details" : step === 3 ? "Appearance" : "Initial Links"}
        </p>

        {/* Step Indicator */}
        <div className="flex items-center justify-center space-x-2 pt-2">
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`h-2 rounded-full transition-all duration-300 ${
                s === step
                  ? "w-10 bg-indigo-500"
                  : s < step
                  ? "w-6 bg-indigo-500/40"
                  : "w-6 bg-slate-800"
              }`}
            />
          ))}
        </div>
      </div>

      {submitError && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-sm flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      {/* Step Contents */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-6 sm:p-8 shadow-xl">
        {/* STEP 1: TYPE SELECTION */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 font-display">1. Choose Hub Type</h2>
              <p className="text-xs text-slate-400 mt-1">
                The hub type defines the resources it manages. Note: Hub type is fixed at creation and cannot be changed later.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {HUB_TYPES_INFO.map((info) => {
                const Icon = info.icon;
                const isSelected = hubType === info.type;

                return (
                  <div
                    key={info.type}
                    onClick={() => handleTypeSelect(info.type)}
                    className={`p-5 rounded-xl border cursor-pointer transition-all flex flex-col justify-between space-y-3 ${
                      isSelected
                        ? "bg-indigo-600/15 border-indigo-500 ring-2 ring-indigo-500/20"
                        : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold"
                        style={{ backgroundColor: info.accent }}
                      >
                        <Icon className="w-5 h-5" />
                      </div>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-white">
                          <Check className="w-3.5 h-3.5" />
                        </div>
                      )}
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-sm font-display">{info.title}</h3>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">{info.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* STEP 2: IDENTITY */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 font-display">2. Hub Identity</h2>
              <p className="text-xs text-slate-400 mt-1">Give your hub a name and unique identifier URL slug.</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Hub Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Support KB"
                  className="w-full bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">URL Slug *</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-mono text-slate-500">
                    {hubType}/
                  </span>
                  <input
                    type="text"
                    value={slug}
                    onChange={(e) => {
                      setIsSlugManual(true);
                      setSlug(e.target.value);
                    }}
                    placeholder="support-kb"
                    className="w-full bg-slate-950/60 border border-slate-800 rounded-xl pl-24 pr-10 py-2.5 text-sm font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {slugStatus === "checking" && <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />}
                    {slugStatus === "available" && <Check className="w-4 h-4 text-emerald-400" />}
                    {slugStatus === "taken" && <span className="text-xs text-rose-400 font-semibold">Taken</span>}
                    {slugStatus === "invalid" && <span className="text-xs text-amber-400 font-semibold">Invalid</span>}
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Slugs are unique within the <span className="font-semibold text-slate-400">{hubType}</span> type domain.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Describe the purpose of this hub..."
                  className="w-full bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: APPEARANCE */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 font-display">3. Appearance & Accent</h2>
              <p className="text-xs text-slate-400 mt-1">Choose a distinct accent color for header badges and icons.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Accent Color</label>
              <div className="flex space-x-3">
                {ACCENT_OPTIONS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setAccent(c)}
                    className={`w-9 h-9 rounded-xl transition-all flex items-center justify-center ${
                      accent === c ? "ring-2 ring-white scale-110" : "hover:scale-105 opacity-80"
                    }`}
                    style={{ backgroundColor: c }}
                  >
                    {accent === c && <Check className="w-4 h-4 text-white" />}
                  </button>
                ))}
              </div>
            </div>

            {/* Live Preview Card */}
            <div className="pt-4 border-t border-slate-800/60">
              <label className="block text-xs font-semibold text-slate-400 mb-2">Live Preview</label>
              <div className="p-5 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center space-x-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center font-bold text-white text-lg shadow-lg"
                  style={{ backgroundColor: accent }}
                >
                  {(name || "Hub").charAt(0).toUpperCase()}
                </div>
                <div>
                  <h4 className="font-bold text-slate-100 font-display">{name || "Hub Name"}</h4>
                  <p className="text-xs font-mono text-slate-500">{hubType}/{slug || "slug"}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: INITIAL LINKS */}
        {step === 4 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 font-display">4. Initial Hub Links (Optional)</h2>
              <p className="text-xs text-slate-400 mt-1">
                Grant this new {hubType} hub access to target hubs per the platform direction matrix.
              </p>
            </div>

            {legalTargetTypes.length === 0 ? (
              <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded-xl text-xs text-slate-400">
                <span className="font-semibold text-slate-300">Ingestion Hubs</span> cannot link out to other hubs; other hubs link <em>into</em> Ingestion Hubs. You can proceed without links.
              </div>
            ) : eligibleTargetHubs.length === 0 ? (
              <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded-xl text-xs text-slate-400">
                No eligible target hubs of type ({legalTargetTypes.join(", ")}) exist yet. You can set up links later.
              </div>
            ) : (
              <div className="space-y-3">
                {eligibleTargetHubs.map((targetHub) => {
                  const isLinked = selectedLinks.some((l) => l.target_hub_id === targetHub.id);

                  return (
                    <div
                      key={targetHub.id}
                      onClick={() => toggleLink(targetHub.id)}
                      className={`p-4 rounded-xl border cursor-pointer flex items-center justify-between transition-colors ${
                        isLinked
                          ? "bg-indigo-600/15 border-indigo-500"
                          : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <Link2 className="w-4 h-4 text-indigo-400" />
                        <div>
                          <span className="font-semibold text-sm text-slate-100">{targetHub.name}</span>
                          <span className="ml-2 text-xs font-mono text-slate-500">
                            {targetHub.hub_type}/{targetHub.slug}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {isLinked && (
                          <span className="px-2 py-0.5 text-xs font-bold text-indigo-300 bg-indigo-950/50 rounded border border-indigo-800/40">
                            Access: Use
                          </span>
                        )}
                        <div
                          className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                            isLinked ? "bg-indigo-500 border-indigo-500 text-white" : "border-slate-700"
                          }`}
                        >
                          {isLinked && <Check className="w-3.5 h-3.5" />}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Wizard Controls */}
        <div className="flex items-center justify-between border-t border-slate-800/80 pt-6 mt-8">
          {step > 1 ? (
            <button
              onClick={() => setStep((s) => s - 1)}
              disabled={isSubmitting}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-sm rounded-xl transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
          ) : (
            <div />
          )}

          {step < 4 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 2 && (!name || slugStatus === "taken" || slugStatus === "invalid")}
              className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-sm rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
            >
              <span>Next</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex items-center space-x-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 text-white font-semibold text-sm rounded-xl transition-all shadow-lg shadow-indigo-500/25"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating Hub...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Finish & Create Hub</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export { HubCreateWizard as HubCreate };
