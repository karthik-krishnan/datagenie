/**
 * Tests for llmStorage.js
 *
 * Covers regressions from:
 * - Migration: API keys must live in browser localStorage only, never on the server.
 * - getLLMConfig must return safe defaults when localStorage is empty or corrupt.
 * - setLLMConfig / getLLMConfig round-trip must preserve all fields.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { getLLMConfig, setLLMConfig, clearLLMConfig } from "./llmStorage.js";

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

  it("overwrites previous value", () => {
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
    expect(cfg.api_key).toBe("");       // default filled in
    expect(cfg.extra_config).toEqual({}); // default filled in
  });
});
