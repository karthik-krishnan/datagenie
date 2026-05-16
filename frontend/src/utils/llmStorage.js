const LS_KEY = "datagenie_llm";

const DEFAULT = { provider: "demo", api_key: "", model: "", extra_config: {} };

// Storage format (new):
// { provider: "azure", configs: { azure: { api_key, model, extra_config }, anthropic: {...}, ... } }
//
// Old flat format is migrated transparently on first read/write.

function _read() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { provider: "demo", configs: {} };
    const stored = JSON.parse(raw);
    // Migrate old flat format → per-provider configs
    if (!stored.configs) {
      const configs = {};
      if (stored.provider) {
        configs[stored.provider] = {
          api_key: stored.api_key || "",
          model: stored.model || "",
          extra_config: stored.extra_config || {},
        };
      }
      return { provider: stored.provider || "demo", configs };
    }
    return stored;
  } catch {
    return { provider: "demo", configs: {} };
  }
}

// Returns the active provider's flattened config — shape expected by the rest of the app.
export function getLLMConfig() {
  const stored = _read();
  const provider = stored.provider || "demo";
  const cfg = stored.configs?.[provider] || {};
  return {
    provider,
    api_key: cfg.api_key || "",
    model: cfg.model || "",
    extra_config: cfg.extra_config || {},
  };
}

// Returns the saved config for a specific provider (used by the settings modal
// when switching provider cards so each provider's key/model/extras are restored).
export function getProviderConfig(provider) {
  const stored = _read();
  const cfg = stored.configs?.[provider] || {};
  return {
    api_key: cfg.api_key || "",
    model: cfg.model || "",
    extra_config: cfg.extra_config || {},
  };
}

// Saves the current provider's config without touching other providers' entries.
// Always clears activePresetId — manual save means user owns the config now.
export function setLLMConfig(config) {
  try {
    const stored = _read();
    const configs = { ...(stored.configs || {}) };
    configs[config.provider] = {
      api_key: config.api_key || "",
      model: config.model || "",
      extra_config: config.extra_config || {},
    };
    localStorage.setItem(LS_KEY, JSON.stringify({ provider: config.provider, configs, activePresetId: null }));
  } catch {
    // storage quota exceeded or private browsing — silently ignore
  }
}

export function getActivePresetId() {
  try { return _read().activePresetId || null; } catch { return null; }
}

export function setActivePresetId(id) {
  try {
    const stored = _read();
    localStorage.setItem(LS_KEY, JSON.stringify({ ...stored, activePresetId: id }));
  } catch {}
}

export function clearLLMConfig() {
  localStorage.removeItem(LS_KEY);
}

// ── App-level feature settings (separate key, separate concern) ───────────────
const APP_SETTINGS_KEY = "datagenie_settings";

const DEFAULT_APP_SETTINGS = {
  complianceEnabled: true,
};

export function getAppSettings() {
  try {
    const raw = localStorage.getItem(APP_SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_APP_SETTINGS };
    return { ...DEFAULT_APP_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_APP_SETTINGS };
  }
}

export function setAppSettings(settings) {
  try {
    localStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // storage quota exceeded or private browsing — silently ignore
  }
}

// ── LLM Presets (named snapshots of a full provider config) ──────────────────
const PRESETS_KEY = "datagenie_llm_presets";

export function getLLMPresets() {
  try {
    return JSON.parse(localStorage.getItem(PRESETS_KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveCurrentAsPreset(name, config) {
  try {
    const presets = getLLMPresets();
    const preset = {
      id: Date.now().toString(),
      name: name.trim(),
      provider: config.provider || "demo",
      api_key: config.api_key || "",
      model: config.model || "",
      extra_config: config.extra_config || {},
    };
    const updated = [...presets, preset];
    localStorage.setItem(PRESETS_KEY, JSON.stringify(updated));
    return updated;
  } catch {
    return getLLMPresets();
  }
}

export function deleteLLMPreset(id) {
  try {
    const updated = getLLMPresets().filter((p) => p.id !== id);
    localStorage.setItem(PRESETS_KEY, JSON.stringify(updated));
    return updated;
  } catch {
    return getLLMPresets();
  }
}
