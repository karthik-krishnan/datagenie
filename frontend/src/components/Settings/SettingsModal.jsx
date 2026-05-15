import { useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { getLLMConfig, getProviderConfig } from "../../utils/llmStorage.js";
import { api } from "../../api/client.js";
import ProviderCard from "./ProviderCard.jsx";
import Spinner from "../common/Spinner.jsx";
import { getAppSettings } from "../../utils/llmStorage.js";

const PROVIDERS = [
  { id: "anthropic", title: "Anthropic", subtitle: "Claude Sonnet/Opus", models: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022"] },
  { id: "openai", title: "OpenAI", subtitle: "GPT-4o / GPT-4", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  { id: "azure", title: "Azure OpenAI", subtitle: "Endpoint + key", models: [] },
  { id: "azure_foundry", title: "Azure AI Foundry", subtitle: "AI Foundry endpoint + key", models: [] },
  { id: "google", title: "Google", subtitle: "Gemini 1.5 Pro/Flash", models: ["gemini-1.5-pro", "gemini-1.5-flash"] },
  { id: "ollama", title: "Ollama", subtitle: "Local, no key", models: ["llama3", "mistral", "codellama"] },
  { id: "demo", title: "Demo", subtitle: "Sample, no key", models: [] },
];

export default function SettingsModal() {
  const setShowSettings = useAppStore((s) => s.setShowSettings);
  const setLLMSettings = useAppStore((s) => s.setLLMSettings);
  const setAppSettings = useAppStore((s) => s.setAppSettings);

  // Feature toggles — lazy-init from localStorage
  const [complianceEnabled, setComplianceEnabled] = useState(
    () => getAppSettings().complianceEnabled !== false
  );
  const [ruleBasedFallbackEnabled, setRuleBasedFallbackEnabled] = useState(
    () => getAppSettings().ruleBasedFallbackEnabled === true
  );

  // Lazy-init from localStorage so the masked badge is visible on the very first render
  // (rather than flashing an empty input while the effect fires).
  const [provider, setProvider] = useState(() => getLLMConfig().provider || "demo");
  const [apiKey, setApiKey] = useState(() => getLLMConfig().api_key || "");
  const [editingKey, setEditingKey] = useState(false); // true = show input, false = show masked badge
  const [model, setModel] = useState(() => getLLMConfig().model || "");
  const [extra, setExtra] = useState(() => {
    const saved = getLLMConfig();
    return { endpoint: "", deployment: "", base_url: "http://localhost:11434", ...(saved.extra_config || {}) };
  });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [err, setErr] = useState(null);
  // No sync effect needed — the component is only mounted while the modal is
  // open (conditional render in App.jsx), so lazy useState always reads fresh
  // values from localStorage on each open.

  const current = PROVIDERS.find((p) => p.id === provider);
  const needsKey = provider !== "demo" && provider !== "ollama";
  const keyReady = !needsKey || apiKey.trim().length > 0;

  const selectProvider = (id) => {
    if (id === provider) return; // already selected — no-op
    // Load this provider's previously saved config (key, model, extras)
    const saved = getProviderConfig(id);
    setProvider(id);
    setApiKey(saved.api_key || "");
    setModel(saved.model || PROVIDERS.find((x) => x.id === id)?.models?.[0] || "");
    setExtra({ endpoint: "", deployment: "", base_url: "http://localhost:11434", ...(saved.extra_config || {}) });
    setEditingKey(false);
    setTestResult(null);
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setErr(null);
    try {
      const data = await api.testConnection(provider, apiKey.trim(), model, extra);
      setTestResult({ ok: data.ok ?? false, message: data.message ?? "Unknown response" });
    } catch (e) {
      setTestResult({ ok: false, message: e.message || String(e) });
    } finally {
      setTesting(false);
    }
  };

  const save = () => {
    // If the user clicked "Change" but left the field blank, preserve the previously saved key.
    const prevKey = getProviderConfig(provider).api_key || "";
    const config = { provider, api_key: apiKey.trim() || prevKey, model, extra_config: extra };
    setLLMSettings(config); // writes per-provider to localStorage + updates store
    setAppSettings({ complianceEnabled, ruleBasedFallbackEnabled }); // persist feature flags
    setShowSettings(false);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      {/* Modal: flex-col so the footer is always visible regardless of content height */}
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">

        {/* ── Scrollable content area ─────────────────────────────────────── */}
        <div className="overflow-y-auto flex-1 min-h-0 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Settings</h2>
            <button onClick={() => setShowSettings(false)} className="text-gray-500 hover:text-gray-800 text-2xl leading-none">×</button>
          </div>

          {/* localStorage disclaimer */}
          <div className="bg-blue-50 border border-blue-200 text-blue-800 rounded-lg px-4 py-3 mb-4 text-sm flex items-start gap-2">
            <span className="text-base">🔒</span>
            <span>Your API key is stored only in <strong>this browser's localStorage</strong> — it is never sent to or stored on our servers. Clearing browser data will remove it.</span>
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

                {apiKey && !editingKey ? (
                  /* Key exists in localStorage — show masked badge */
                  <div className="flex items-center gap-2 border border-green-300 bg-green-50 rounded-lg px-3 py-2">
                    <span className="text-green-700 text-sm">✓</span>
                    <span className="flex-1 text-sm text-green-800 font-medium tracking-widest">••••••••••••••••</span>
                    <span className="text-xs text-green-600 mr-2">Saved in browser</span>
                    <button
                      type="button"
                      onClick={() => { setEditingKey(true); setApiKey(""); setTestResult(null); }}
                      className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 bg-white hover:bg-indigo-50"
                    >
                      Change
                    </button>
                  </div>
                ) : (
                  /* No key or user clicked Change */
                  <div>
                    {editingKey && (
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs text-amber-700">Enter a new key to replace the saved one.</span>
                        <button
                          type="button"
                          onClick={() => {
                            const saved = getLLMConfig();
                            setApiKey(saved.provider === provider ? (saved.api_key || "") : "");
                            setEditingKey(false);
                          }}
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
                      autoFocus
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

            {/* Azure AI Foundry extras */}
            {provider === "azure_foundry" && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Foundry Endpoint</label>
                  <input
                    value={extra.endpoint || ""}
                    onChange={(e) => setExtra({ ...extra, endpoint: e.target.value })}
                    placeholder="https://your-resource.services.ai.azure.com/models"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Model Name <span className="text-gray-400 font-normal">(optional)</span></label>
                  <input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="e.g. gpt-4o, Llama-3.3-70B-Instruct, claude-opus-4-7"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
                  />
                  {model.toLowerCase().startsWith("claude") && (
                    <p className="mt-1.5 text-xs text-indigo-600 flex items-start gap-1">
                      <span>ℹ️</span>
                      <span>Claude models use the Anthropic Messages API automatically — the endpoint above is used as the base URL.</span>
                    </p>
                  )}
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

            {testResult && (
              <div className={`rounded-lg px-3 py-2 text-sm border ${testResult.ok ? "bg-green-50 border-green-200 text-green-800" : "bg-red-50 border-red-200 text-red-700"}`}>
                {testResult.ok ? "✓" : "✗"} {testResult.message}
              </div>
            )}

            {/* ── Features ─────────────────────────────────────────────────── */}
            <div className="border-t border-gray-100 pt-4 mt-2">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Features</h3>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-800">Regulatory Compliance</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Show sensitivity tagging, DLP frameworks, and compliance review steps.
                    Turn off for simpler use cases.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setComplianceEnabled((v) => !v)}
                  className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors ml-4 ${complianceEnabled ? "bg-indigo-500" : "bg-gray-300"}`}
                  role="switch"
                  aria-checked={complianceEnabled}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${complianceEnabled ? "translate-x-5" : "translate-x-0"}`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between mt-4">
                <div>
                  <p className="text-sm font-medium text-gray-800">Rule-Based Fallback</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    When enabled, schema inference falls back to built-in rules if the LLM
                    fails — with a visible warning. When disabled, LLM failures surface as
                    an explicit error so you know exactly what went wrong.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setRuleBasedFallbackEnabled((v) => !v)}
                  className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors ml-4 ${ruleBasedFallbackEnabled ? "bg-indigo-500" : "bg-gray-300"}`}
                  role="switch"
                  aria-checked={ruleBasedFallbackEnabled}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${ruleBasedFallbackEnabled ? "translate-x-5" : "translate-x-0"}`}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ── Sticky footer — always visible ──────────────────────────────── */}
        <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4 rounded-b-2xl flex justify-between items-center">
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
            <button onClick={save} className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
              Save Settings
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
