/**
 * Tests for llmStorage.js
 *
 * Covers regressions from:
 * - Migration: API keys must live in browser localStorage only, never on the server.
 * - getLLMConfig must return safe defaults when localStorage is empty or corrupt.
 * - setLLMConfig / getLLMConfig round-trip must preserve all fields.
 * - Per-provider storage: each provider's key/model/extras are stored independently
 *   so switching providers never wipes another provider's key.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { getLLMConfig, setLLMConfig, clearLLMConfig, getProviderConfig } from "./llmStorage.js";

const DEFAULT = { provider: "demo", api_key: "", model: "", extra_config: {} };

beforeEach(() => {
  localStorage.clear();
});

// ─── getLLMConfig defaults ────────────────────────────────────────────────────

describe("getLLMConfig — empty storage", () => {
  it("returns demo provider when localStorage is empty", () => {
    expect(getLLMConfig().provider).toBe("demo");
  });

  it("returns empty api_key when localStorage is empty", () => {
    expect(getLLMConfig().api_key).toBe("");
  });

  it("returns empty model when localStorage is empty", () => {
    expect(getLLMConfig().model).toBe("");
  });

  it("returns empty extra_config object when localStorage is empty", () => {
    expect(getLLMConfig().extra_config).toEqual({});
  });

  it("handles corrupted JSON without throwing", () => {
    localStorage.setItem("datagenie_llm", "{not valid json");
    expect(() => getLLMConfig()).not.toThrow();
    expect(getLLMConfig().provider).toBe("demo");
  });
});

// ─── setLLMConfig / getLLMConfig round-trip ───────────────────────────────────

describe("setLLMConfig → getLLMConfig round-trip", () => {
  it("persists provider", () => {
    setLLMConfig({ ...DEFAULT, provider: "anthropic" });
    expect(getLLMConfig().provider).toBe("anthropic");
  });

  it("persists api_key", () => {
    setLLMConfig({ ...DEFAULT, provider: "anthropic", api_key: "sk-ant-test-123" });
    expect(getLLMConfig().api_key).toBe("sk-ant-test-123");
  });

  it("persists model", () => {
    setLLMConfig({ ...DEFAULT, provider: "openai", model: "gpt-4o" });
    expect(getLLMConfig().model).toBe("gpt-4o");
  });

  it("persists extra_config", () => {
    const extra = { endpoint: "https://my.openai.azure.com", deployment: "gpt4-dep" };
    setLLMConfig({ ...DEFAULT, provider: "azure", extra_config: extra });
    expect(getLLMConfig().extra_config).toEqual(extra);
  });

  it("switching active provider returns the new provider's config", () => {
    setLLMConfig({ ...DEFAULT, provider: "anthropic", api_key: "old-key" });
    setLLMConfig({ ...DEFAULT, provider: "openai",    api_key: "new-key" });
    const cfg = getLLMConfig();
    expect(cfg.provider).toBe("openai");
    expect(cfg.api_key).toBe("new-key");
  });

  it("stores data under the correct localStorage key", () => {
    setLLMConfig({ ...DEFAULT, provider: "google" });
    const raw = localStorage.getItem("datagenie_llm");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw).provider).toBe("google");
  });
});

// ─── clearLLMConfig ────────────────────────────────────────────────────────────

describe("clearLLMConfig", () => {
  it("removes data from localStorage", () => {
    setLLMConfig({ ...DEFAULT, provider: "anthropic", api_key: "sk-ant-test" });
    clearLLMConfig();
    expect(localStorage.getItem("datagenie_llm")).toBeNull();
  });

  it("getLLMConfig returns defaults after clear", () => {
    setLLMConfig({ ...DEFAULT, provider: "anthropic", api_key: "sk-ant-test" });
    clearLLMConfig();
    expect(getLLMConfig().provider).toBe("demo");
    expect(getLLMConfig().api_key).toBe("");
  });
});

// ─── Default merging ──────────────────────────────────────────────────────────

describe("getLLMConfig — partial data in storage", () => {
  it("merges missing fields with defaults", () => {
    localStorage.setItem("datagenie_llm", JSON.stringify({ provider: "ollama" }));
    const cfg = getLLMConfig();
    expect(cfg.provider).toBe("ollama");
    expect(cfg.api_key).toBe("");         // default filled in
    expect(cfg.extra_config).toEqual({}); // default filled in
  });
});

// ─── Per-provider key isolation ───────────────────────────────────────────────

describe("per-provider key isolation", () => {
  it("saving one provider does not wipe another provider's key", () => {
    setLLMConfig({ provider: "anthropic", api_key: "sk-ant-123", model: "claude-3-5-sonnet-20241022", extra_config: {} });
    setLLMConfig({ provider: "openai",    api_key: "sk-oai-456", model: "gpt-4o",                    extra_config: {} });
    // Switch back to anthropic — its key must still be there
    setLLMConfig({ provider: "anthropic", api_key: "sk-ant-123", model: "claude-3-5-sonnet-20241022", extra_config: {} });
    expect(getLLMConfig().api_key).toBe("sk-ant-123");
  });

  it("saving demo mode does not wipe azure key", () => {
    const azureExtra = { endpoint: "https://kk.openai.azure.com", deployment: "gpt-4o" };
    setLLMConfig({ provider: "azure", api_key: "az-key-789", model: "", extra_config: azureExtra });
    // User switches to demo and saves
    setLLMConfig({ provider: "demo",  api_key: "",           model: "", extra_config: {} });
    // Switch back to azure — key and extras must survive
    const azure = getProviderConfig("azure");
    expect(azure.api_key).toBe("az-key-789");
    expect(azure.extra_config).toEqual(azureExtra);
  });

  it("each provider independently stores its own model", () => {
    setLLMConfig({ provider: "anthropic", api_key: "k1", model: "claude-3-5-sonnet-20241022", extra_config: {} });
    setLLMConfig({ provider: "google",    api_key: "k2", model: "gemini-1.5-pro",             extra_config: {} });
    expect(getProviderConfig("anthropic").model).toBe("claude-3-5-sonnet-20241022");
    expect(getProviderConfig("google").model).toBe("gemini-1.5-pro");
  });
});

// ─── getProviderConfig ────────────────────────────────────────────────────────

describe("getProviderConfig", () => {
  it("returns saved config for the specified provider", () => {
    setLLMConfig({ provider: "openai", api_key: "sk-oai", model: "gpt-4o", extra_config: {} });
    const cfg = getProviderConfig("openai");
    expect(cfg.api_key).toBe("sk-oai");
    expect(cfg.model).toBe("gpt-4o");
  });

  it("returns empty config for a provider that has never been saved", () => {
    const cfg = getProviderConfig("google");
    expect(cfg.api_key).toBe("");
    expect(cfg.model).toBe("");
    expect(cfg.extra_config).toEqual({});
  });

  it("returns the correct provider even when a different provider is active", () => {
    setLLMConfig({ provider: "anthropic", api_key: "sk-ant", model: "claude-opus-4-20250514", extra_config: {} });
    setLLMConfig({ provider: "demo",      api_key: "",       model: "",                       extra_config: {} });
    // Active is demo, but anthropic config should still be retrievable
    expect(getProviderConfig("anthropic").api_key).toBe("sk-ant");
  });

  it("returns azure extra_config independently of active provider", () => {
    const extras = { endpoint: "https://res.openai.azure.com", deployment: "gpt-4o" };
    setLLMConfig({ provider: "azure", api_key: "az-key", model: "", extra_config: extras });
    setLLMConfig({ provider: "openai", api_key: "oai-key", model: "gpt-4o", extra_config: {} });
    expect(getProviderConfig("azure").extra_config).toEqual(extras);
  });
});

// ─── Old flat-format migration ────────────────────────────────────────────────

describe("old flat-format migration", () => {
  it("reads api_key from old flat format without throwing", () => {
    localStorage.setItem("datagenie_llm", JSON.stringify({
      provider: "anthropic",
      api_key: "sk-legacy-key",
      model: "claude-3-5-sonnet-20241022",
      extra_config: {},
    }));
    expect(getLLMConfig().provider).toBe("anthropic");
    expect(getLLMConfig().api_key).toBe("sk-legacy-key");
  });

  it("migrates old format so subsequent setLLMConfig preserves the legacy key", () => {
    localStorage.setItem("datagenie_llm", JSON.stringify({
      provider: "anthropic",
      api_key: "sk-legacy-key",
      model: "claude-3-5-sonnet-20241022",
      extra_config: {},
    }));
    // Save a different provider — legacy key must survive in per-provider storage
    setLLMConfig({ provider: "openai", api_key: "sk-oai", model: "gpt-4o", extra_config: {} });
    expect(getProviderConfig("anthropic").api_key).toBe("sk-legacy-key");
  });
});
