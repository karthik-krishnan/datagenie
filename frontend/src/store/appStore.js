import { create } from "zustand";
import { getLLMConfig, setLLMConfig } from "../utils/llmStorage.js";

export const useAppStore = create((set, get) => ({
  currentStage: 1,
  sessionId: null,
  uploadedFiles: [],
  contextText: "",
  inferredSchema: null,
  characteristics: { volume: 100, distributions: {}, temporal: {}, quickMode: false },
  complianceRules: {},
  selectedFrameworks: [],   // frameworks the user confirmed apply to their dataset
  relationships: [],
  outputConfig: {
    formats: ["csv"],
    packaging: "one_file_per_entity",
    json_options: { json_mode: "array" },
    xml_options: { xml_root: "root", xml_row: "row" },
  },
  llmSettings: getLLMConfig(),
  previewData: null,
  isLoading: false,
  error: null,
  showSettings: false,

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
  setComplianceRules: (r) => set({ complianceRules: r }),
  setSelectedFrameworks: (f) => set({ selectedFrameworks: f }),
  setRelationships: (r) => set({ relationships: r }),
  setOutputConfig: (c) => set({ outputConfig: { ...get().outputConfig, ...c } }),
  setLLMSettings: (s) => { setLLMConfig(s); set({ llmSettings: s }); },
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
      characteristics: { volume: 100, distributions: {}, temporal: {}, quickMode: false },
      complianceRules: {},
      selectedFrameworks: [],
      relationships: [],
      previewData: null,
      error: null,
    }),
}));
