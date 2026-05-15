import { getLLMConfig, getAppSettings } from "../utils/llmStorage.js";

// In Docker / local dev: relative /api (proxied by nginx → backend container).
// In static-site deployments (Vercel, Netlify, etc.): set VITE_API_URL to the
// backend origin, e.g. https://datagenie-zvt6.onrender.com
const BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/\/$/, "") + "/api"
  : "/api";

async function handle(res) {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data);
    } catch (_) {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

// Retry a fetch call up to `retries` times with exponential backoff.
// Retries on network errors ("failed to fetch") and 502/503/504 (deploy restarts).
async function fetchWithRetry(fn, retries = 2, delayMs = 2000) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const isNetworkError = err instanceof TypeError; // "failed to fetch"
      const isServerError  = err?.message?.startsWith("HTTP 5");
      if ((isNetworkError || isServerError) && attempt < retries) {
        await new Promise((r) => setTimeout(r, delayMs * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
}

export const api = {
  getConfig: () =>
    fetchWithRetry(() => fetch(`${BASE}/config`).then(handle)),

  createSession: () =>
    fetchWithRetry(() => fetch(`${BASE}/sessions/`, { method: "POST" }).then(handle)),

  inferSchema: (files, contextText, sessionId) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    fd.append("context_text", contextText || "");
    if (sessionId) fd.append("session_id", sessionId);

    // Attach LLM config from localStorage so backend uses the right provider/key
    const llm = getLLMConfig();
    fd.append("llm_provider", llm.provider || "demo");
    fd.append("llm_api_key", llm.api_key || "");
    fd.append("llm_model", llm.model || "");
    fd.append("llm_extra_config", JSON.stringify(llm.extra_config || {}));

    // Pass rule-based fallback setting so backend enforces strict vs permissive mode
    const appSettings = getAppSettings();
    fd.append("allow_fallback", appSettings.ruleBasedFallbackEnabled ? "true" : "false");

    return fetch(`${BASE}/schema/infer`, { method: "POST", body: fd }).then(handle);
  },

  // Returns the built-in demo template for a keyword — never calls an LLM.
  // Used by ProfilePicker starter cards so they work regardless of LLM config.
  getDemoSchema: (keyword = "") =>
    fetch(`${BASE}/schema/demo?keyword=${encodeURIComponent(keyword)}`).then(handle),

  // Settings — kept for test connection only; save/load now handled via localStorage
  getSettings: () => fetch(`${BASE}/settings/`).then(handle),

  preview: (payload) => {
    const llm = getLLMConfig();
    return fetch(`${BASE}/generate/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, llm_config: llm }),
    }).then(handle);
  },

  listProfiles: () => fetchWithRetry(() => fetch(`${BASE}/profiles/`).then(handle)),
  getProfile: (id) => fetch(`${BASE}/profiles/${id}`).then(handle),
  createProfile: (data) =>
    fetch(`${BASE}/profiles/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(handle),
  updateProfile: (id, data) =>
    fetch(`${BASE}/profiles/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(handle),
  deleteProfile: (id) =>
    fetch(`${BASE}/profiles/${id}`, { method: "DELETE" }).then(handle),
  useProfile: (id) =>
    fetch(`${BASE}/profiles/${id}/use`, { method: "POST" }).then(handle),

  testConnection: (provider, apiKey, model, extraConfig) =>
    fetch(`${BASE}/settings/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey, model, extra_config: extraConfig }),
    }).then(handle),

  normalizeRule: (ruleText) => {
    const llm = getLLMConfig();
    return fetch(`${BASE}/schema/normalize-rule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rule: ruleText,
        llm_provider: llm.provider || "demo",
        llm_api_key: llm.api_key || "",
        llm_model: llm.model || "",
        llm_extra_config: llm.extra_config || {},
      }),
    }).then(handle);
  },

  generate: async (payload) => {
    const llm = getLLMConfig();
    const res = await fetch(`${BASE}/generate/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, llm_config: llm }),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const cd = res.headers.get("content-disposition") || "";
    const m = cd.match(/filename="?([^";]+)"?/i);
    const filename = m ? m[1] : "test_data.bin";
    return { blob, filename };
  },
};
