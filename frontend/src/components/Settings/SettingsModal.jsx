import { useEffect, useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { api } from "../../api/client.js";
import ProviderCard from "./ProviderCard.jsx";
import Spinner from "../common/Spinner.jsx";

const PROVIDERS = [
  { id: "anthropic", title: "Anthropic", subtitle: "Claude Sonnet/Opus", models: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022"] },
  { id: "openai", title: "OpenAI", subtitle: "GPT-4o / GPT-4", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  { id: "azure", title: "Azure OpenAI", subtitle: "Endpoint + key", models: [] },
  { id: "google", title: "Google", subtitle: "Gemini 1.5 Pro/Flash", models: ["gemini-1.5-pro", "gemini-1.5-flash"] },
  { id: "ollama", title: "Ollama", subtitle: "Local, no key", models: ["llama3", "mistral", "codellama"] },
  { id: "demo", title: "Demo", subtitle: "Sample, no key", models: [] },
];

export default function SettingsModal() {
  const showSettings = useAppStore((s) => s.showSettings);
  const setShowSettings = useAppStore((s) => s.setShowSettings);
  const setLLMSettings = useAppStore((s) => s.setLLMSettings);

  const [provider, setProvider] = useState("demo");
  const [apiKey, setApiKey] = useState("");
  const [hasSavedKey, setHasSavedKey] = useState(false);   // key exists in DB but is masked
  const [replacingKey, setReplacingKey] = useState(false); // user clicked "Change key"
  const [savedProvider, setSavedProvider] = useState(null); // which provider the DB key belongs to
  const [model, setModel] = useState("");
  const [extra, setExtra] = useState({ endpoint: "", deployment: "", base_url: "http://localhost:11434" });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [err, setErr] = useState(null);

  // Load saved settings when modal opens
  useEffect(() => {
    if (!showSettings) return;
    setTestResult(null);
    setErr(null);
    api.getSettings().then((s) => {
      const p = s.provider || "demo";
      setProvider(p);
      setModel(s.model || "");
      setExtra({ endpoint: "", deployment: "", base_url: "http://localhost:11434", ...(s.extra_config || {}) });
      const keyIsSaved = s.api_key === "***";
      setHasSavedKey(keyIsSaved);
      setSavedProvider(keyIsSaved ? p : null);
      setReplacingKey(false);
      setApiKey("");
    }).catch(() => {});
  }, [showSettings]);

  if (!showSettings) return null;

  const current = PROVIDERS.find((p) => p.id === provider);
  const needsKey = provider !== "demo" && provider !== "ollama";
  const effectiveKeyAvailable = (hasSavedKey && !replacingKey) || apiKey.trim().length > 0;
  const keyReady = !needsKey || effectiveKeyAvailable;

  const selectProvider = (id) => {
    setProvider(id);
    setModel(PROVIDERS.find((x) => x.id === id)?.models?.[0] || "");
    setTestResult(null);
    setApiKey("");
    setReplacingKey(false);
    setHasSavedKey(id === savedProvider);
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setErr(null);
    try {
      // Pass the typed key if provided, otherwise signal backend to use saved key
      const payload = {
        provider,
        api_key: apiKey.trim() || (hasSavedKey ? "USE_SAVED" : ""),
        model,
        extra_config: extra,
      };
      const res = await fetch("/api/settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setTestResult({ ok: data.ok, message: data.message });
    } catch (e) {
      setTestResult({ ok: false, message: e.message });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      // If user left key blank and a saved key exists, don't overwrite it
      const payload = {
        provider,
        api_key: apiKey.trim() || (hasSavedKey ? "KEEP_SAVED" : ""),
        model,
        extra_config: extra,
      };
      await api.saveSettings(payload);
      setLLMSettings(payload);
      setShowSettings(false);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">LLM Provider Settings</h2>
          <button onClick={() => setShowSettings(false)} className="text-gray-500 hover:text-gray-800 text-2xl leading-none">×</button>
        </div>

        {provider === "demo" && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg px-4 py-3 mb-4 text-sm">
            Running on sample generation — no API key required.
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 mb-6">
          {PROVIDERS.map((p) => (
            <ProviderCard
              key={p.id}
              id={p.id}
              title={p.title}
              subtitle={p.subtitle}
              selected={provider === p.id}
              onSelect={selectProvider}
            />
          ))}
        </div>

        <div className="space-y-4">
          {/* API Key field */}
          {needsKey && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>

              {hasSavedKey && !replacingKey ? (
                /* Saved key — show masked display with a Change button */
                <div className="flex items-center gap-2 border border-green-300 bg-green-50 rounded-lg px-3 py-2">
                  <span className="text-green-700 text-sm">✓</span>
                  <span className="flex-1 text-sm text-green-800 font-medium tracking-widest">••••••••••••••••</span>
                  <span className="text-xs text-green-600 mr-2">API key saved</span>
                  <button
                    type="button"
                    onClick={() => { setReplacingKey(true); setApiKey(""); }}
                    className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 bg-white hover:bg-indigo-50"
                  >
                    Change
                  </button>
                </div>
              ) : (
                /* No saved key, or user clicked Change */
                <div>
                  {replacingKey && (
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs text-amber-700">Entering a new key will replace the saved one.</span>
                      <button
                        type="button"
                        onClick={() => { setReplacingKey(false); setApiKey(""); }}
                        className="text-xs text-gray-400 hover:text-gray-600 underline"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter API key"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                    autoFocus={replacingKey}
                  />
                </div>
              )}
            </div>
          )}

          {/* Azure extras */}
          {provider === "azure" && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Azure Endpoint</label>
                <input
                  value={extra.endpoint || ""}
                  onChange={(e) => setExtra({ ...extra, endpoint: e.target.value })}
                  placeholder="https://your-resource.openai.azure.com"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Deployment Name</label>
                <input
                  value={extra.deployment || ""}
                  onChange={(e) => setExtra({ ...extra, deployment: e.target.value })}
                  placeholder="gpt-4o-deployment"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                />
              </div>
            </>
          )}

          {/* Ollama extras */}
          {provider === "ollama" && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
                <input
                  value={extra.base_url || ""}
                  onChange={(e) => setExtra({ ...extra, base_url: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                />
              </div>
            </>
          )}

          {/* Model selector */}
          {current?.models?.length > 0 && provider !== "ollama" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
              >
                {current.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          )}

          {err && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">{err}</div>}

          {/* Test connection result */}
          {testResult && (
            <div className={`rounded-lg px-3 py-2 text-sm border ${testResult.ok ? "bg-green-50 border-green-200 text-green-800" : "bg-red-50 border-red-200 text-red-700"}`}>
              {testResult.ok ? "✓" : "✗"} {testResult.message}
            </div>
          )}

          <div className="flex justify-between items-center pt-2">
            <button
              onClick={testConnection}
              disabled={testing || provider === "demo" || !keyReady}
              title={!keyReady ? "Enter an API key first" : ""}
              className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-40 text-sm"
            >
              {testing ? <><Spinner /> Testing…</> : "🔌 Test Connection"}
            </button>
            <div className="flex gap-2">
              <button onClick={() => setShowSettings(false)} className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">Cancel</button>
              <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50">
                {saving ? <Spinner /> : "Save Settings"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
