/**
 * Tests for appStore.js
 *
 * Covers regressions from:
 * - setLLMSettings must write to localStorage (browser-only key storage).
 * - loadProfile must unpack __selectedFrameworks from the compliance_rules blob
 *   (avoids DB schema migration — we pack it in).
 * - reset must clear workflow state but preserve LLM settings.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { getLLMConfig } from "../utils/llmStorage.js";

// We import the store after clearing localStorage so the initial state is predictable.
let useAppStore;

beforeEach(async () => {
  localStorage.clear();
  // Re-import store fresh each test to reset Zustand state
  const mod = await import("./appStore.js?" + Math.random());
  useAppStore = mod.useAppStore;
});

// ─── setLLMSettings ───────────────────────────────────────────────────────────

describe("setLLMSettings", () => {
  it("updates llmSettings in the store", () => {
    const { setLLMSettings } = useAppStore.getState();
    setLLMSettings({ provider: "anthropic", api_key: "sk-test", model: "claude-3-5-sonnet-20241022", extra_config: {} });
    expect(useAppStore.getState().llmSettings.provider).toBe("anthropic");
  });

  it("persists api_key to localStorage", () => {
    const { setLLMSettings } = useAppStore.getState();
    setLLMSettings({ provider: "openai", api_key: "sk-openai-123", model: "gpt-4o", extra_config: {} });
    expect(getLLMConfig().api_key).toBe("sk-openai-123");
  });

  it("persists provider to localStorage", () => {
    const { setLLMSettings } = useAppStore.getState();
    setLLMSettings({ provider: "google", api_key: "", model: "gemini-1.5-pro", extra_config: {} });
    expect(getLLMConfig().provider).toBe("google");
  });
});

// ─── loadProfile — __selectedFrameworks unpacking ─────────────────────────────

describe("loadProfile — __selectedFrameworks", () => {
  const makeProfile = (frameworks, complianceRules = {}) => ({
    id: "prof-1",
    name: "Test Profile",
    description: "for testing",
    schema_config: null,
    characteristics: JSON.stringify({ volume: 50 }),
    compliance_rules: JSON.stringify({
      ...complianceRules,
      __selectedFrameworks: frameworks,
    }),
    relationships: JSON.stringify([]),
    output_config: JSON.stringify({}),
  });

  it("unpacks __selectedFrameworks from compliance_rules blob", () => {
    const { loadProfile } = useAppStore.getState();
    loadProfile(makeProfile(["PII", "HIPAA", "GDPR"]));
    expect(useAppStore.getState().selectedFrameworks).toEqual(["PII", "HIPAA", "GDPR"]);
  });

  it("does not include __selectedFrameworks in complianceRules store key", () => {
    const { loadProfile } = useAppStore.getState();
    loadProfile(makeProfile(["PII"], { ssn: { action: "mask" } }));
    const rules = useAppStore.getState().complianceRules;
    expect("__selectedFrameworks" in rules).toBe(false);
    expect(rules.ssn).toEqual({ action: "mask" });
  });

  it("defaults to empty array when __selectedFrameworks missing", () => {
    const { loadProfile } = useAppStore.getState();
    const profileWithoutFrameworks = {
      id: "prof-2",
      name: "Old Profile",
      description: null,
      schema_config: null,
      characteristics: JSON.stringify({}),
      compliance_rules: JSON.stringify({ ssn: { action: "mask" } }),
      relationships: JSON.stringify([]),
      output_config: JSON.stringify({}),
    };
    loadProfile(profileWithoutFrameworks);
    expect(useAppStore.getState().selectedFrameworks).toEqual([]);
  });

  it("sets currentStage to 2 when schema_config exists", () => {
    const { loadProfile } = useAppStore.getState();
    const profileWithSchema = {
      ...makeProfile(["PII"]),
      schema_config: JSON.stringify({ tables: [] }),
    };
    loadProfile(profileWithSchema);
    expect(useAppStore.getState().currentStage).toBe(2);
  });

  it("sets currentStage to 1 when no schema_config", () => {
    const { loadProfile } = useAppStore.getState();
    loadProfile(makeProfile(["PII"]));
    expect(useAppStore.getState().currentStage).toBe(1);
  });
});

// ─── reset ────────────────────────────────────────────────────────────────────

describe("reset", () => {
  it("clears inferredSchema", () => {
    const store = useAppStore.getState();
    store.setInferredSchema({ tables: [] });
    store.reset();
    expect(useAppStore.getState().inferredSchema).toBeNull();
  });

  it("clears contextText", () => {
    const store = useAppStore.getState();
    store.setContextText("some context");
    store.reset();
    expect(useAppStore.getState().contextText).toBe("");
  });

  it("clears selectedFrameworks", () => {
    const store = useAppStore.getState();
    store.setSelectedFrameworks(["PII", "GDPR"]);
    store.reset();
    expect(useAppStore.getState().selectedFrameworks).toEqual([]);
  });

  it("does NOT clear llmSettings", () => {
    // LLM settings survive a reset — user shouldn't have to re-enter their key
    const store = useAppStore.getState();
    store.setLLMSettings({ provider: "anthropic", api_key: "sk-test", model: "claude-3-5-sonnet-20241022", extra_config: {} });
    store.reset();
    expect(useAppStore.getState().llmSettings.provider).toBe("anthropic");
  });
});
