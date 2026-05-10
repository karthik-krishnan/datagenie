const LS_KEY = "datagenie_llm";

const DEFAULT = { provider: "demo", api_key: "", model: "", extra_config: {} };

export function getLLMConfig() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT };
    return { ...DEFAULT, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT };
  }
}

export function setLLMConfig(config) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(config));
  } catch {
    // storage quota exceeded or private browsing — silently ignore
  }
}

export function clearLLMConfig() {
  localStorage.removeItem(LS_KEY);
}
