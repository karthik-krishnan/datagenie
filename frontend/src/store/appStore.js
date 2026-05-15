import { create } from "zustand";
import { getLLMConfig, setLLMConfig, getAppSettings, setAppSettings } from "../utils/llmStorage.js";

/**
 * Sort columns so PK appears first, then FK columns (_id), then everything else.
 * Works on arrays of column objects (with .name) or plain name strings.
 *
 * Scoring:
 *   0 — own PK: exactly "id" or "{tableName}_id"
 *   1 — any other *_id column (FK)
 *   2 — everything else
 */
export function sortColumnsForDisplay(columns, tableName) {
  const tname = (tableName || "").toLowerCase().replace(/s$/, ""); // strip trailing 's'
  const score = (name) => {
    const n = (name || "").toLowerCase();
    if (n === "id" || n === `${tname}_id` || n === `${tname}id`) return 0;
    if (n.endsWith("_id") || n.endsWith("id")) return 1;
    return 2;
  };
  return [...columns].sort((a, b) => {
    const na = typeof a === "string" ? a : a.name;
    const nb = typeof b === "string" ? b : b.name;
    return score(na) - score(nb);
  });
}

export const useAppStore = create((set, get) => ({
  currentStage: 1,
  sessionId: null,
  uploadedFiles: [],
  contextText: "",
  inferredSchema: null,
  characteristics: { volume: 100, distributions: {}, temporal: {}, ranges: {}, quickMode: false, per_parent_counts: {} },
  complianceRules: {},
  selectedFrameworks: [],   // frameworks the user confirmed apply to their dataset
  relationships: [],
  outputConfig: {
    formats: ["csv"],
    json_options: { json_mode: "array" },
    xml_options: { xml_root: "root", xml_row: "row" },
  },
  llmSettings: getLLMConfig(),
  appSettings: getAppSettings(),
  previewData: null,
  isLoading: false,
  error: null,
  showSettings: false,
  maxVolumeRecords: 10000,   // updated from /api/config on mount

  // Profile state
  profileId: null,
  profileName: null,
  profileDescription: null,
  showProfilePicker: true,
  showSaveProfileModal: false,

  setStage: (n) => set({ currentStage: n }),
  setSessionId: (id) => set({ sessionId: id }),
  setUploadedFiles: (files) => set({ uploadedFiles: files }),
  setContextText: (t) => set({ contextText: t }),
  setInferredSchema: (s) => set({ inferredSchema: s, relationships: s?.relationships || [] }),
  updateSchema: (updater) => set((st) => ({ inferredSchema: updater(st.inferredSchema) })),
  setCharacteristics: (c) => set({ characteristics: { ...get().characteristics, ...c } }),
  setComplianceRules: (r) =>
    typeof r === "function"
      ? set((state) => ({ complianceRules: r(state.complianceRules) }))
      : set({ complianceRules: r }),
  setSelectedFrameworks: (f) => set({ selectedFrameworks: f }),
  setRelationships: (r) => set({ relationships: r }),

  /**
   * Apply the result of an /api/schema/infer call — populates schema,
   * characteristics, compliance rules, frameworks, and relationships.
   * Used by both App.jsx (normal flow) and ProfilePicker (demo shortcuts).
   *
   * @param result  - raw JSON from the infer endpoint
   * @param goToStage - stage to navigate to after applying (default: 1)
   */
  applyInferResult: (result, goToStage = 1) => {
    const state = get();
    const ext = result.extracted || {};

    // Sort each table's columns: PK first, FK (_id) second, rest last
    const tables = (result.tables || []).map((t) => ({
      ...t,
      columns: sortColumnsForDisplay(t.columns, t.table_name),
    }));

    // Build characteristics patch
    const charPatch = { ...state.characteristics };
    if (ext.volume) charPatch.volume = ext.volume;

    if (ext.distributions && Object.keys(ext.distributions).length > 0) {
      const formatted = {};
      for (const [rawKey, vals] of Object.entries(ext.distributions)) {
        let key = rawKey;
        if (!rawKey.includes(".")) {
          let tableName = tables[0]?.table_name || "records";
          for (const t of tables) {
            if (t.columns?.some((c) => c.name.toLowerCase() === rawKey.toLowerCase())) {
              tableName = t.table_name;
              break;
            }
          }
          key = `${tableName}.${rawKey}`;
        }
        const fractional = {};
        for (const [val, pct] of Object.entries(vals)) {
          fractional[val] = Number(pct) / 100;
        }
        formatted[key] = fractional;
      }
      charPatch.distributions = formatted;
    }
    if (ext.per_parent_counts && Object.keys(ext.per_parent_counts).length > 0) {
      charPatch.per_parent_counts = ext.per_parent_counts;
    }

    set({
      inferredSchema: { ...result, tables },
      relationships: result.relationships || [],
      characteristics: charPatch,
      ...(ext.compliance_rules && Object.keys(ext.compliance_rules).length > 0
        ? { complianceRules: ext.compliance_rules }
        : {}),
      ...(result.frameworks_detected?.length > 0
        ? { selectedFrameworks: result.frameworks_detected }
        : {}),
      currentStage: goToStage,
    });
  },
  setMaxVolumeRecords: (n) => set({ maxVolumeRecords: n }),
  setOutputConfig: (c) => set({ outputConfig: { ...get().outputConfig, ...c } }),
  setLLMSettings: (s) => { setLLMConfig(s); set({ llmSettings: s }); },
  setAppSettings: (s) => { setAppSettings(s); set({ appSettings: s }); },
  setPreviewData: (p) => set({ previewData: p }),
  setLoading: (b) => set({ isLoading: b }),
  setError: (e) => set({ error: e }),
  setShowSettings: (b) => set({ showSettings: b }),

  setProfileId: (id) => set({ profileId: id }),
  setProfileName: (name) => set({ profileName: name }),
  setProfileDescription: (desc) => set({ profileDescription: desc }),
  setShowProfilePicker: (v) => set({ showProfilePicker: v }),
  setShowSaveProfileModal: (v) => set({ showSaveProfileModal: v }),
  loadProfile: (profile) => {
    // compliance_rules blob also carries __selectedFrameworks to avoid a DB migration
    const complianceBlob = profile.compliance_rules ? JSON.parse(profile.compliance_rules) : {};
    const { __selectedFrameworks: selectedFrameworks = [], ...complianceRules } = complianceBlob;
    return set({
      profileId: profile.id,
      profileName: profile.name,
      profileDescription: profile.description,
      inferredSchema: profile.schema_config ? JSON.parse(profile.schema_config) : null,
      characteristics: profile.characteristics ? JSON.parse(profile.characteristics) : {},
      complianceRules,
      selectedFrameworks,
      relationships: profile.relationships ? JSON.parse(profile.relationships) : [],
      outputConfig: profile.output_config ? JSON.parse(profile.output_config) : {},
      showProfilePicker: false,
      currentStage: profile.schema_config ? 2 : 1,
    });
  },
  clearProfile: () =>
    set({
      profileId: null,
      profileName: null,
      profileDescription: null,
    }),

  reset: () =>
    set({
      currentStage: 1,
      uploadedFiles: [],
      contextText: "",
      inferredSchema: null,
      characteristics: { volume: 100, distributions: {}, temporal: {}, ranges: {}, quickMode: false, per_parent_counts: {} },
      complianceRules: {},
      selectedFrameworks: [],
      relationships: [],
      previewData: null,
      error: null,
    }),
}));
