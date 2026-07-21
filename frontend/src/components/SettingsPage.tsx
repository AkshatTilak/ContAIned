import React, { useState, useEffect } from "react";
import { Settings, Save, RotateCcw, CheckCircle, Shield, Globe, Server } from "lucide-react";
import { useStore } from "../store/useStore";
import { useToast } from "./shared";
import { telemetryService } from "../services/telemetry";
import { api } from "../services/api";

export const SettingsPage: React.FC = () => {
  const gatewayUrl = useStore((state) => state.gatewayUrl);
  const apiKey = useStore((state) => state.apiKey);
  const updateSettings = useStore((state) => state.updateSettings);
  const resetSettings = useStore((state) => state.resetSettings);
  const { success, info, error } = useToast();

  const [inputGatewayUrl, setInputGatewayUrl] = useState(gatewayUrl);
  const [inputApiKey, setInputApiKey] = useState(apiKey);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    setInputGatewayUrl(gatewayUrl);
    setInputApiKey(apiKey);
  }, [gatewayUrl, apiKey]);

  const handleSave = () => {
    updateSettings({ gatewayUrl: inputGatewayUrl, apiKey: inputApiKey });
    telemetryService.disconnect();
    telemetryService.connect();
    success(
      "Settings Saved",
      "Gateway API configuration and authorization parameters updated successfully."
    );
  };

  const handleReset = () => {
    resetSettings();
    const defaults = useStore.getState();
    setInputGatewayUrl(defaults.gatewayUrl);
    setInputApiKey(defaults.apiKey);
    info(
      "Reset to Defaults",
      "System environment settings restored to default values."
    );
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    try {
      const health = await api.getSystemHealth();
      success(
        "Connection Successful",
        `Gateway reachable (Status: ${health.status}, Active Services: ${Object.keys(health.services || {}).length})`
      );
    } catch (err) {
      error(
        "Connection Failed",
        `Unable to reach Gateway API at ${inputGatewayUrl}. Please check host and port.`
      );
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto py-4">
      {/* Header Banner */}
      <div className="flex items-center justify-between bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 shadow-md">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-tr from-emerald-500/20 to-indigo-500/20 border border-emerald-500/30 text-emerald-400">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold font-display text-[var(--text-primary)]">
              Gateway & Environment Settings
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Manage platform connection endpoints, authentication credentials, and environment overrides.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Defaults</span>
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Settings</span>
          </button>
        </div>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Gateway Endpoint Config */}
        <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-3 font-display">
            <Globe className="w-4 h-4 text-emerald-400" />
            <span>API Gateway Connection</span>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                Gateway Base URL
              </label>
              <input
                type="text"
                value={inputGatewayUrl}
                onChange={(e) => setInputGatewayUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className="w-full px-3.5 py-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 transition-all font-mono"
              />
              <p className="text-[11px] text-[var(--text-muted)] mt-1">
                Base URL endpoint for FastAPI gateway (defaults to http://localhost:8000).
              </p>
            </div>
            <button
              onClick={handleTestConnection}
              disabled={isTesting}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] text-xs text-emerald-400 font-medium transition-all"
            >
              {isTesting ? (
                <div className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <CheckCircle className="w-3.5 h-3.5" />
              )}
              <span>{isTesting ? "Testing Connection..." : "Test Gateway Connectivity"}</span>
            </button>
          </div>
        </div>

        {/* Security & Authentication */}
        <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-3 font-display">
            <Shield className="w-4 h-4 text-indigo-400" />
            <span>Authentication Credentials</span>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                X-API-Key Authorization Token
              </label>
              <input
                type="password"
                value={inputApiKey}
                onChange={(e) => setInputApiKey(e.target.value)}
                placeholder="sk_live_default_key"
                className="w-full px-3.5 py-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-indigo-500 transition-all font-mono"
              />
              <p className="text-[11px] text-[var(--text-muted)] mt-1">
                Header key sent as <code className="text-zinc-300 font-mono">X-API-Key</code> on all REST & WebSocket requests.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Platform Information Box */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 space-y-3 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-3 font-display">
          <Server className="w-4 h-4 text-zinc-400" />
          <span>ContAIned V4 Platform Architecture</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-[var(--text-muted)] block text-[10px] uppercase tracking-wider">Version</span>
            <span className="font-semibold text-emerald-400">4.1.0-PROD</span>
          </div>
          <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-[var(--text-muted)] block text-[10px] uppercase tracking-wider">State Management</span>
            <span className="font-semibold text-[var(--text-primary)]">Zustand 5.0</span>
          </div>
          <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-[var(--text-muted)] block text-[10px] uppercase tracking-wider">Routing System</span>
            <span className="font-semibold text-[var(--text-primary)]">React Router 7</span>
          </div>
          <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-[var(--text-muted)] block text-[10px] uppercase tracking-wider">Animations</span>
            <span className="font-semibold text-[var(--text-primary)]">Framer Motion</span>
          </div>
        </div>
      </div>
    </div>
  );
};
