import { useEffect, useState } from "react";
import { useAppStore } from "./store/appStore.js";
import { api } from "./api/client.js";
import StageIndicator from "./components/common/StageIndicator.jsx";
import Spinner from "./components/common/Spinner.jsx";
import SettingsModal from "./components/Settings/SettingsModal.jsx";
import LLMPresetSwitcher from "./components/Settings/LLMPresetSwitcher.jsx";
import UploadZone from "./components/Stage1_Upload/UploadZone.jsx";
import ContextInput from "./components/Stage1_Upload/ContextInput.jsx";
import SchemaCard from "./components/Stage1_Upload/SchemaCard.jsx";
import VolumeInput from "./components/Stage2_Characteristics/VolumeInput.jsx";
import AttributeDistribution from "./components/Stage2_Characteristics/AttributeDistribution.jsx";
import ComplianceReviewPanel from "./components/Stage3_Compliance/ComplianceReviewPanel.jsx";
import RelationshipMapper from "./components/Stage4_Relationships/RelationshipMapper.jsx";
import FormatPicker from "./components/Stage5_Output/FormatPicker.jsx";
import PreviewTable from "./components/Stage5_Output/PreviewTable.jsx";
import GenerateButton from "./components/Stage5_Output/GenerateButton.jsx";
import ProfilePicker from "./components/Profiles/ProfilePicker.jsx";
import ProfileBanner from "./components/Profiles/ProfileBanner.jsx";
import SaveProfileModal from "./components/Profiles/SaveProfileModal.jsx";
import UnderstandingSummary from "./components/Stage2_Characteristics/UnderstandingSummary.jsx";

/**
 * Given a root volume, the relationship graph, and per-parent counts,
 * compute the absolute row count for every table.
 *
 * Returned object: { [tableName]: number }
 * Only includes tables that differ from the base `volume` — so the backend
 * applies its own default (3× per level) for any table not listed.
 */
/** Get expected children per parent from a spec (number or {min,max,shape}). */
function expectedCount(spec) {
  if (!spec && spec !== 0) return 3;
  if (typeof spec === "number") return spec;
  const min = Number(spec.min) || 1;
  const max = Number(spec.max) || min;
  const shape = spec.shape || "Realistic";
  if (shape === "Fixed") return Math.round((min + max) / 2);
  if (shape === "Uniform") return (min + max) / 2;
  // Realistic: skewed toward low end (~35% of range above min)
  return min + 0.35 * (max - min);
}

function computePerTableVolumes(relationships, volume, perParentCounts) {
  if (!relationships || relationships.length === 0) return {};

  const manyToOne = relationships.filter(
    (r) => r.cardinality === "one_to_many" || !r.cardinality
  );
  if (manyToOne.length === 0) return {};

  // Build parent→children map
  const childrenOf = {}; // parent → [child]
  for (const r of manyToOne) {
    if (!childrenOf[r.source_table]) childrenOf[r.source_table] = [];
    childrenOf[r.source_table].push(r.target_table);
  }

  // Root tables = not a child in any one_to_many
  const childSet = new Set(manyToOne.map((r) => r.target_table));
  const allTableNames = [
    ...new Set([
      ...manyToOne.map((r) => r.source_table),
      ...manyToOne.map((r) => r.target_table),
    ]),
  ];
  const roots = allTableNames.filter((t) => !childSet.has(t));

  // BFS to compute absolute volumes using expected child counts
  const volumes = {};
  const queue = roots.map((r) => ({ table: r, vol: volume }));
  while (queue.length) {
    const { table, vol } = queue.shift();
    volumes[table] = vol;
    for (const child of childrenOf[table] || []) {
      const avg = expectedCount(perParentCounts[child]);
      queue.push({ table: child, vol: vol * avg });
    }
  }

  // Only return non-root overrides (root tables use `volume` directly)
  const overrides = {};
  for (const [t, v] of Object.entries(volumes)) {
    if (!roots.includes(t)) overrides[t] = Math.round(v);
  }
  return overrides;
}

export default function App() {
  const {
    currentStage, setStage,
    sessionId, setSessionId,
    uploadedFiles, setUploadedFiles,
    contextText, setContextText,
    inferredSchema, setInferredSchema, updateSchema,
    characteristics, setCharacteristics,
    complianceRules, setComplianceRules,
    selectedFrameworks, setSelectedFrameworks,
    relationships, setRelationships,
    outputConfig, setOutputConfig,
    previewData, setPreviewData,
    isLoading, setLoading,
    inferStatus, setInferStatus,
    error, setError,
    showSettings, setShowSettings,
    llmSettings,
    appSettings,
    llmPresets, activePresetId,
    showProfilePicker, setShowProfilePicker,
    profileId,
    setShowSaveProfileModal,
    reset,
    applyInferResult,
    maxVolumeRecords,
  } = useAppStore();

  const [schemaTab, setSchemaTab] = useState(0);
  // Snapshot of context + files used for the last successful inference.
  // Re-infer is only enabled when something has changed since then.
  const [lastInferredState, setLastInferredState] = useState(null);

  useEffect(() => {
    if (!sessionId) {
      api.createSession().then((s) => setSessionId(s.session_id)).catch(() => {});
    }
  }, [sessionId, setSessionId]);

  // Fetch server-side config once on mount (volume cap, etc.)
  const { setMaxVolumeRecords } = useAppStore();
  useEffect(() => {
    api.getConfig()
      .then((cfg) => { if (cfg?.max_volume_records) setMaxVolumeRecords(cfg.max_volume_records); })
      .catch(() => {}); // silently keep the default on failure
  }, []);

  // Reset schema tab when schema changes (e.g. re-infer or new template)
  useEffect(() => {
    setSchemaTab(0);
  }, [inferredSchema]);

  // When a profile or template loads a schema externally, mark state as
  // already-inferred so the Re-infer button starts disabled.
  useEffect(() => {
    if (inferredSchema) {
      setLastInferredState({
        contextText,
        fileKey: uploadedFiles.map((f) => f.name).join("|"),
      });
    } else {
      setLastInferredState(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inferredSchema]);

  // Wipe stale preview whenever the user navigates away from the Output stage
  useEffect(() => {
    if (currentStage !== 5) {
      setPreviewData(null);
    }
  }, [currentStage]);

  if (showProfilePicker) {
    return <ProfilePicker />;
  }

  const complianceEnabled = appSettings?.complianceEnabled !== false;
  const piiAvailable = complianceEnabled && !!(inferredSchema?.pii_detected || inferredSchema?.sensitive_detected);
  const relAvailable = uploadedFiles.length > 1 || (inferredSchema?.tables?.length || 0) > 1 || /relationship/i.test(contextText || "");
  const multiEntity = (inferredSchema?.tables?.length || 0) > 1;

  const currentFileKey = uploadedFiles.map((f) => f.name).join("|");
  const hasChangedSinceInfer = !lastInferredState
    || lastInferredState.contextText !== contextText
    || lastInferredState.fileKey !== currentFileKey;

  const nextStage = (cur) => {
    if (cur === 2 && !piiAvailable) return relAvailable ? 4 : 5;
    if (cur === 3 && !relAvailable) return 5;
    return cur + 1;
  };
  const prevStage = (cur) => {
    if (cur === 5 && !relAvailable) return piiAvailable ? 3 : 2;
    if (cur === 4 && !piiAvailable) return 2;
    return cur - 1;
  };

  const runInfer = async () => {
    if (uploadedFiles.length === 0 && !contextText.trim()) {
      setError("Please upload a file or describe your data in the context box.");
      return;
    }
    setError(null);
    setLoading(true);

    // Progress messages — cycle through known backend steps with realistic timing
    const INFER_STEPS = [
      { msg: "Analysing your description…",               delay: 0 },
      { msg: "Detecting domain and compliance frameworks…", delay: 1800 },
      { msg: "Inferring schema columns and types…",        delay: 4500 },
      { msg: "Classifying sensitive fields…",              delay: 8000 },
      { msg: "Validating compliance rules…",               delay: 12000 },
      { msg: "Finalising schema…",                         delay: 16000 },
    ];
    setInferStatus(INFER_STEPS[0].msg);
    const timers = INFER_STEPS.slice(1).map(({ msg, delay }) =>
      setTimeout(() => setInferStatus(msg), delay)
    );

    try {
      const result = await api.inferSchema(uploadedFiles, contextText, sessionId);

      // Surface LLM provider configuration warnings (e.g. missing Azure endpoint)
      if (result.llm_warning) {
        setError(`⚠️ LLM configuration issue: ${result.llm_warning} Schema was inferred using built-in rules only.`);
      }

      // Apply schema result — populates schema, characteristics, compliance, relationships
      // Stay on Stage 1 so the user can review and edit the inferred schema.
      applyInferResult(result, 1);
      // Snapshot so Re-infer stays disabled until user edits something
      setLastInferredState({
        contextText,
        fileKey: uploadedFiles.map((f) => f.name).join("|"),
      });
    } catch (e) {
      setError(e.message);
    } finally {
      timers.forEach(clearTimeout);
      setInferStatus(null);
      setLoading(false);
    }
  };

  const runPreview = async () => {
    if (!inferredSchema) {
      setError("Please infer a schema first (go back to Stage 1).");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const perTableVols = computePerTableVolumes(
        relationships, characteristics.volume || 100, characteristics.per_parent_counts || {}
      );
      const payload = {
        schema: inferredSchema,
        characteristics: { ...characteristics, per_table_volumes: perTableVols },
        compliance_rules: complianceRules,
        relationships,
        volume: characteristics.volume || 100,
        formats: outputConfig.formats,
        output_options: { ...outputConfig.json_options, ...outputConfig.xml_options },
      };
      const r = await api.preview(payload);
      setPreviewData(r.preview);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const runGenerate = async () => {
    if (!inferredSchema) {
      setError("Please infer a schema first (go back to Stage 1).");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const perTableVols = computePerTableVolumes(
        relationships, characteristics.volume || 100, characteristics.per_parent_counts || {}
      );
      const payload = {
        schema: inferredSchema,
        characteristics: { ...characteristics, per_table_volumes: perTableVols },
        compliance_rules: complianceRules,
        relationships,
        volume: characteristics.volume || 100,
        formats: outputConfig.formats,
        output_options: { ...outputConfig.json_options, ...outputConfig.xml_options },
      };
      const { blob, filename } = await api.generate(payload);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const providerLabel = {
    anthropic: "Anthropic",
    openai:    "OpenAI",
    azure:         "Azure OpenAI",
    azure_foundry: "Azure AI Foundry",
    google:    "Google",
    ollama:    "Ollama",
    demo:      "Demo",
  }[llmSettings?.provider] ?? llmSettings?.provider ?? "Demo";

  const isDemo       = !llmSettings?.provider || llmSettings.provider === "demo";
  const activePreset = activePresetId ? llmPresets.find((p) => p.id === activePresetId) : null;
  const modelLabel   = !isDemo && llmSettings?.model ? llmSettings.model : null;

  return (
    <div className="h-screen bg-white text-gray-900 flex flex-col overflow-hidden">
      <header className="border-b border-gray-200 px-6 py-3 flex items-center justify-between bg-white">
        <button
          onClick={() => { reset(); setShowProfilePicker(true); }}
          className="text-lg font-semibold flex items-center gap-2 hover:text-indigo-600 transition-colors shrink-0"
          title="Back to home"
        >
          <img src="/favicon.svg" alt="Datagenia" className="w-8 h-8" />
          <div className="flex flex-col items-start shrink-0">
            <span>Datagenia</span>
            <span className="text-xs font-normal text-gray-400 leading-none whitespace-nowrap">AI-powered synthetic test data generator</span>
          </div>
        </button>

      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-60 bg-gray-100 border-r border-gray-200 flex flex-col">
          <div className="p-4 flex-1">
            <button
              onClick={() => { reset(); setShowProfilePicker(true); }}
              className="flex items-center gap-1.5 text-sm text-indigo-500 hover:text-indigo-700 transition-colors mb-4 group"
            >
              <span className="group-hover:-translate-x-0.5 transition-transform">←</span>
              <span>Templates &amp; Profiles</span>
            </button>
            <StageIndicator />
          </div>

          {/* Settings pinned to sidebar bottom */}
          <div className="border-t border-gray-200 p-3">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowSettings(true)}
                className="flex-1 flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-gray-200 transition-colors"
                title="Open Settings"
              >
                <span className="text-lg">⚙️</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-700">Settings</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isDemo ? "bg-amber-400" : "bg-emerald-400"}`} />
                    <span className="text-xs text-gray-500 truncate" title={activePreset ? activePreset.name : providerLabel}>
                      {activePreset ? activePreset.name : providerLabel}
                    </span>
                  </div>
                  {!activePreset && modelLabel && (
                    <div className="text-xs text-gray-400 truncate mt-0.5" title={modelLabel}>{modelLabel}</div>
                  )}
                </div>
              </button>
              <LLMPresetSwitcher currentConfig={llmSettings} />
            </div>
          </div>
        </aside>

        <main className="flex-1 p-6 overflow-y-auto">
          {profileId && <ProfileBanner />}

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
              {error}
            </div>
          )}

          {currentStage === 1 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold">Describe Your Data</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Tell Datagenia about your data in any combination:
                </p>
                <ul className="mt-2 space-y-1 text-sm text-gray-500">
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0">{"📎"}</span>
                    <span><span className="font-medium text-gray-700">Upload a sample file</span> — CSV, Excel, JSON, XML, YAML — columns and types are auto-extracted</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0">{"✏️"}</span>
                    <span><span className="font-medium text-gray-700">Describe in plain English</span> — e.g. 20 customers each with 1-3 orders and an email address</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0">{"🔀"}</span>
                    <span><span className="font-medium text-gray-700">Or both together</span> — file gives structure; text fills in volume, relationships, and intent</span>
                  </li>
                </ul>
              </div>
              <UploadZone files={uploadedFiles} onFiles={setUploadedFiles} />
              {profileId && inferredSchema && (
                <p className="text-xs text-gray-500">
                  Upload new files to override the saved schema
                </p>
              )}
              <ContextInput value={contextText} onChange={setContextText} />

              {/* Inline Infer Schema shortcut — visible right after editing context, no scrolling needed */}
              {inferredSchema && (
                <div className="flex flex-col items-end gap-1 -mt-2">
                  <button
                    onClick={runInfer}
                    disabled={isLoading || !hasChangedSinceInfer}
                    className="inline-flex items-center gap-1.5 h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 text-base font-medium transition-colors"
                  >
                    {isLoading ? <Spinner /> : <><span className="text-base leading-none">↻</span> Infer Schema</>}
                  </button>
                  {inferStatus && (
                    <span className="flex items-center gap-1.5 text-xs text-indigo-500 animate-pulse">
                      <Spinner />
                      {inferStatus}
                    </span>
                  )}
                </div>
              )}

              {inferredSchema && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium">Inferred schema</h3>
                    {llmSettings?.provider === "demo" && (
                      <span className="text-xs bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-2.5 py-0.5">
                        🪄 Demo — sample schema. Connect an LLM to infer from your actual input.
                      </span>
                    )}
                  </div>
                  {/* Dog-ear tabs — same pattern as AttributeDistribution */}
                  <div>
                    {inferredSchema.tables.length > 1 && (
                      <div className="flex items-end gap-1 pl-3 overflow-x-auto">
                        {inferredSchema.tables.map((t, i) => (
                          <button
                            key={t.table_name}
                            onClick={() => setSchemaTab(i)}
                            className={[
                              "flex items-center px-4 py-2 text-sm font-medium whitespace-nowrap",
                              "border rounded-t-lg transition-all select-none",
                              schemaTab === i
                                ? "bg-white border-gray-200 [border-bottom-color:white] text-gray-900 relative z-10 -mb-px"
                                : "bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-50 hover:text-gray-700 mt-1",
                            ].join(" ")}
                          >
                            {t.table_name}
                          </button>
                        ))}
                      </div>
                    )}
                    {(() => {
                      const i = schemaTab;
                      const t = inferredSchema.tables[i];
                      if (!t) return null;
                      return (
                        <div className={inferredSchema.tables.length > 1 ? "border border-gray-200 rounded-b-xl rounded-tr-xl overflow-hidden" : ""}>
                          <SchemaCard
                            key={i}
                            table={t}
                            complianceEnabled={complianceEnabled}
                            onChange={(updated) => {
                              const renames = {};
                              updated.columns.forEach((col, idx) => {
                                const old = t.columns[idx];
                                if (old && old.name !== col.name) renames[old.name] = col.name;
                              });
                              updateSchema((s) => {
                                const next = {
                                  ...s,
                                  tables: s.tables.map((tt, idx) => (idx === i ? updated : tt)),
                                };
                                if (Object.keys(renames).length > 0 && s.extracted?.compliance_rules) {
                                  const patched = {};
                                  for (const [k, v] of Object.entries(s.extracted.compliance_rules)) {
                                    patched[renames[k] ?? k] = v;
                                  }
                                  next.extracted = { ...s.extracted, compliance_rules: patched };
                                }
                                return next;
                              });
                              if (Object.keys(renames).length > 0) {
                                const patched = {};
                                for (const [k, v] of Object.entries(complianceRules)) {
                                  patched[renames[k] ?? k] = v;
                                }
                                setComplianceRules(patched);
                              }
                            }}
                          />
                        </div>
                      );
                    })()}
                  </div>

                  {inferredSchema.relationships?.length > 0 && (
                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                      <h4 className="text-sm font-medium mb-2">Detected cross-file relationships</h4>
                      <ul className="text-sm space-y-1">
                        {inferredSchema.relationships.map((r, i) => (
                          <li key={i} className="text-gray-700">
                            Looks like {r.source_table}.{r.source_column} → {r.target_table}.{r.target_column} ({r.cardinality.replace(/_/g, " ")})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {inferStatus && (
                <div className="flex items-center gap-2 text-sm text-indigo-600 animate-pulse mb-1">
                  <Spinner />
                  <span>{inferStatus}</span>
                </div>
              )}
              <div className="flex justify-end gap-2">
                {!inferredSchema ? (
                  <button
                    onClick={runInfer}
                    disabled={isLoading || (uploadedFiles.length === 0 && !contextText.trim())}
                    className="inline-flex items-center h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 text-base font-medium"
                  >
                    {isLoading ? <Spinner /> : "Infer Schema"}
                  </button>
                ) : (
                  <button onClick={() => setStage(nextStage(1))} className="inline-flex items-center h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 text-base font-medium">
                    Continue →
                  </button>
                )}
              </div>
            </div>
          )}

          {currentStage === 2 && inferredSchema && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold">Characteristics</h2>
                <p className="text-sm text-gray-500 mt-1">Configure volume and value distributions.</p>
              </div>

              <UnderstandingSummary
                extracted={inferredSchema.extracted}
                schema={inferredSchema}
              />

              <VolumeInput
                value={characteristics.volume ?? ""}
                onChange={(v) => setCharacteristics({ volume: v })}
                fromContext={!!inferredSchema?.extracted?.volume}
                relationships={relationships}
                schema={inferredSchema}
                perParentCounts={characteristics.per_parent_counts || {}}
                maxVolume={maxVolumeRecords}
                onChildCountChange={(childTable, spec) =>
                  setCharacteristics({
                    per_parent_counts: {
                      ...(characteristics.per_parent_counts || {}),
                      [childTable]: spec,
                    },
                  })
                }
              />
              <div className="border border-gray-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-gray-800">Value Distributions</h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {characteristics.quickMode
                        ? "AI will pick realistic distributions automatically."
                        : "Specify how values should be spread across categories."}
                    </p>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <span className="text-xs text-gray-500">Let AI decide</span>
                    <div
                      onClick={() => setCharacteristics({ quickMode: !characteristics.quickMode })}
                      className={`relative w-10 h-5 rounded-full transition-colors ${characteristics.quickMode ? "bg-indigo-500" : "bg-gray-300"}`}
                    >
                      <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${characteristics.quickMode ? "translate-x-5" : "translate-x-0"}`} />
                    </div>
                  </label>
                </div>

                {!characteristics.quickMode && (
                  <div className="pt-1">
                    <AttributeDistribution
                      tables={inferredSchema.tables}
                      characteristics={characteristics}
                      onUpdate={(patch) => setCharacteristics(patch)}
                      onSchemaUpdate={(tableIdx, colName, enumValues) => {
                        updateSchema((s) => ({
                          ...s,
                          tables: s.tables.map((tt, idx) =>
                            idx === tableIdx
                              ? {
                                  ...tt,
                                  columns: tt.columns.map((c) =>
                                    c.name === colName
                                      ? { ...c, type: "enum", enum_values: enumValues }
                                      : c
                                  ),
                                }
                              : tt
                          ),
                        }));
                      }}
                    />
                  </div>
                )}
              </div>

              <div className="flex justify-between items-center">
                <button onClick={() => setStage(prevStage(2))} className="inline-flex items-center h-10 px-5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-base font-medium">Back</button>
                <button
                  onClick={() => setStage(nextStage(2))}
                  disabled={(characteristics.volume || 0) > maxVolumeRecords}
                  className="inline-flex items-center h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-base font-medium"
                >Continue →</button>
              </div>
            </div>
          )}

          {currentStage === 3 && piiAvailable && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold">Compliance & Data Sensitivity</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Confirm which regulations apply, then we'll show only the fields that need your attention.
                </p>
              </div>
              <ComplianceReviewPanel
                schema={inferredSchema}
                complianceRules={complianceRules}
                onUpdate={setComplianceRules}
                detectedFrameworks={inferredSchema?.frameworks_detected || []}
                selectedFrameworks={selectedFrameworks}
                onFrameworksChange={setSelectedFrameworks}
                onBack={() => setStage(prevStage(3))}
                onContinue={() => setStage(nextStage(3))}
              />
            </div>
          )}

          {currentStage === 4 && relAvailable && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold">Relationships</h2>
                <p className="text-sm text-gray-500 mt-1">Confirm or edit detected relationships between tables.</p>
              </div>
              <RelationshipMapper
                schema={inferredSchema}
                relationships={relationships}
                onUpdate={setRelationships}
                aiRelationships={inferredSchema?.relationships || []}
              />
              <div className="flex justify-between items-center">
                <button onClick={() => setStage(prevStage(4))} className="inline-flex items-center h-10 px-5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-base font-medium">Back</button>
                <button onClick={() => setStage(nextStage(4))} className="inline-flex items-center h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 text-base font-medium">Continue →</button>
              </div>
            </div>
          )}

          {currentStage === 5 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold">Output & Preview</h2>
                <p className="text-sm text-gray-500 mt-1">Choose output format and preview before generating.</p>
              </div>
              <FormatPicker outputConfig={outputConfig} onChange={setOutputConfig} multiEntity={multiEntity} />

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium">Preview</h3>
                  <button onClick={runPreview} disabled={isLoading} className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50">
                    {isLoading ? <Spinner /> : previewData ? "Regenerate preview" : "Generate preview"}
                  </button>
                </div>
                <PreviewTable data={previewData} />
              </div>

              <div className="flex justify-between items-center">
                <button onClick={() => setStage(prevStage(5))} className="inline-flex items-center h-10 px-5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-base font-medium">Back</button>
                <div className="flex items-center gap-2">
                  {/* Only show Save as Profile when no profile is active.
                      When a profile is loaded, the banner at the top handles Update / Save as New. */}
                  {!profileId && (
                    <button
                      onClick={() => setShowSaveProfileModal(true)}
                      className="inline-flex items-center h-10 px-5 rounded-lg border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50 text-base font-medium"
                    >
                      💾 Save as Profile
                    </button>
                  )}
                  <GenerateButton onClick={runGenerate} loading={isLoading} />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {showSettings && <SettingsModal />}
      <SaveProfileModal />
    </div>
  );
}
