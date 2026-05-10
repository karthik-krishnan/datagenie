import { useEffect } from "react";
import { useAppStore } from "./store/appStore.js";
import { api } from "./api/client.js";
import StageIndicator from "./components/common/StageIndicator.jsx";
import Spinner from "./components/common/Spinner.jsx";
import SettingsModal from "./components/Settings/SettingsModal.jsx";
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
function computePerTableVolumes(relationships, volume, perParentCounts) {
  if (!relationships || relationships.length === 0) return {};

  const manyToOne = relationships.filter(
    (r) => r.cardinality === "many_to_one" || !r.cardinality
  );
  if (manyToOne.length === 0) return {};

  // Build parent→children map
  const childrenOf = {}; // parent → [{child, rel}]
  const parentOf = {};   // child → parent
  for (const r of manyToOne) {
    if (!childrenOf[r.target_table]) childrenOf[r.target_table] = [];
    childrenOf[r.target_table].push(r.source_table);
    parentOf[r.source_table] = r.target_table;
  }

  // Root tables = not a child in any many_to_one
  const childSet = new Set(manyToOne.map((r) => r.source_table));
  const allTableNames = [
    ...new Set([
      ...manyToOne.map((r) => r.source_table),
      ...manyToOne.map((r) => r.target_table),
    ]),
  ];
  const roots = allTableNames.filter((t) => !childSet.has(t));

  // BFS to compute absolute volumes
  const volumes = {};
  const queue = roots.map((r) => ({ table: r, vol: volume }));
  while (queue.length) {
    const { table, vol } = queue.shift();
    volumes[table] = vol;
    for (const child of childrenOf[table] || []) {
      const countPerParent = perParentCounts[child] || 3;
      queue.push({ table: child, vol: vol * countPerParent });
    }
  }

  // Only return non-root overrides (root tables use `volume` directly)
  const overrides = {};
  for (const [t, v] of Object.entries(volumes)) {
    if (!roots.includes(t)) overrides[t] = v;
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
    error, setError,
    showSettings, setShowSettings,
    llmSettings,
    showProfilePicker, setShowProfilePicker,
    profileId,
    setShowSaveProfileModal,
    reset,
    applyInferResult,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId) {
      api.createSession().then((s) => setSessionId(s.session_id)).catch(() => {});
    }
  }, [sessionId, setSessionId]);

  if (showProfilePicker) {
    return <ProfilePicker />;
  }

  const piiAvailable = !!(inferredSchema?.pii_detected || inferredSchema?.sensitive_detected);
  const relAvailable = uploadedFiles.length > 1 || (inferredSchema?.tables?.length || 0) > 1 || /relationship/i.test(contextText || "");
  const multiEntity = (inferredSchema?.tables?.length || 0) > 1;

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
    try {
      const result = await api.inferSchema(uploadedFiles, contextText, sessionId);

      // Surface LLM provider configuration warnings (e.g. missing Azure endpoint)
      if (result.llm_warning) {
        setError(`⚠️ LLM configuration issue: ${result.llm_warning} Schema was inferred using built-in rules only.`);
      }

      // Apply schema result — populates schema, characteristics, compliance, relationships
      // Stay on Stage 1 so the user can review and edit the inferred schema.
      applyInferResult(result, 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const runPreview = async () => {
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
        packaging: outputConfig.packaging,
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
        packaging: outputConfig.packaging,
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
    azure:     "Azure OpenAI",
    google:    "Google",
    ollama:    "Ollama",
    demo:      "Demo",
  }[llmSettings?.provider] ?? llmSettings?.provider ?? "Demo";

  const isDemo      = !llmSettings?.provider || llmSettings.provider === "demo";
  const modelLabel  = !isDemo && llmSettings?.model ? llmSettings.model : null;

  return (
    <div className="min-h-screen bg-white text-gray-900 flex flex-col">
      <header className="border-b border-gray-200 px-6 py-3 flex items-center justify-between bg-white">
        <button
          onClick={() => { reset(); setShowProfilePicker(true); }}
          className="text-lg font-semibold flex items-center gap-2 hover:text-indigo-600 transition-colors"
          title="Back to home"
        >
          <span>🪄</span> DataGenie
        </button>

        <div className="flex items-center gap-3">
          {/* AI provider badge — subtle, clickable to open settings */}
          <button
            onClick={() => setShowSettings(true)}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
            title="Change AI provider"
          >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isDemo ? "bg-amber-400" : "bg-emerald-400"}`} />
            <span className="font-medium">{providerLabel}</span>
            {modelLabel && (
              <span className="text-gray-300">·</span>
            )}
            {modelLabel && (
              <span className="truncate max-w-[140px]">{modelLabel}</span>
            )}
          </button>

          <button
            onClick={() => setShowSettings(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-600 border border-gray-200 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
            title="LLM Provider Settings"
          >
            <span>⚙️</span>
            <span>Settings</span>
          </button>
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="w-60 bg-gray-100 border-r border-gray-200 p-4">
          <StageIndicator />
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
                <h2 className="text-xl font-semibold">Upload & Context</h2>
                <p className="text-sm text-gray-500 mt-1">Upload sample data files and describe your context.</p>
              </div>
              <UploadZone files={uploadedFiles} onFiles={setUploadedFiles} />
              {profileId && inferredSchema && (
                <p className="text-xs text-gray-500">
                  Upload new files to override the saved schema
                </p>
              )}
              <ContextInput value={contextText} onChange={setContextText} />

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
                  {inferredSchema.tables.map((t, i) => (
                    <SchemaCard
                      key={i}
                      table={t}
                      onChange={(updated) => {
                        // Detect any column renames so we can keep compliance rules in sync
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
                          // Patch extracted.compliance_rules keys to new names
                          if (Object.keys(renames).length > 0 && s.extracted?.compliance_rules) {
                            const patched = {};
                            for (const [k, v] of Object.entries(s.extracted.compliance_rules)) {
                              patched[renames[k] ?? k] = v;
                            }
                            next.extracted = { ...s.extracted, compliance_rules: patched };
                          }
                          return next;
                        });

                        // Also rename keys in the complianceRules store
                        if (Object.keys(renames).length > 0) {
                          const patched = {};
                          for (const [k, v] of Object.entries(complianceRules)) {
                            patched[renames[k] ?? k] = v;
                          }
                          setComplianceRules(patched);
                        }
                      }}
                    />
                  ))}

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

              <div className="flex justify-end gap-2">
                <button
                  onClick={runInfer}
                  disabled={isLoading || (uploadedFiles.length === 0 && !contextText.trim())}
                  className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {isLoading ? <Spinner /> : inferredSchema ? "Re-infer" : "Infer Schema"}
                </button>
                {inferredSchema && (
                  <button onClick={() => setStage(nextStage(1))} className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                    Continue
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
                onChildCountChange={(childTable, count) =>
                  setCharacteristics({
                    per_parent_counts: {
                      ...(characteristics.per_parent_counts || {}),
                      [childTable]: count,
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
                  <div className="space-y-4 pt-1">
                    {inferredSchema.tables.map((t, i) => (
                      <AttributeDistribution
                        key={i}
                        table={t}
                        characteristics={characteristics}
                        onUpdate={(patch) => setCharacteristics(patch)}
                      />
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-between">
                <button onClick={() => setStage(prevStage(2))} className="px-5 py-2 rounded-lg border border-gray-300 hover:bg-gray-50">Back</button>
                <button onClick={() => setStage(nextStage(2))} className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Continue</button>
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
              <RelationshipMapper schema={inferredSchema} relationships={relationships} onUpdate={setRelationships} />
              <div className="flex justify-between">
                <button onClick={() => setStage(prevStage(4))} className="px-5 py-2 rounded-lg border border-gray-300 hover:bg-gray-50">Back</button>
                <button onClick={() => setStage(nextStage(4))} className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Continue</button>
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
                    {isLoading ? <Spinner /> : "Regenerate preview"}
                  </button>
                </div>
                <PreviewTable data={previewData} />
              </div>

              <div className="flex justify-between items-center">
                <button onClick={() => setStage(prevStage(5))} className="px-5 py-2 rounded-lg border border-gray-300 hover:bg-gray-50">Back</button>
                <div className="flex items-center gap-2">
                  {/* Only show Save as Profile when no profile is active.
                      When a profile is loaded, the banner at the top handles Update / Save as New. */}
                  {!profileId && (
                    <button
                      onClick={() => setShowSaveProfileModal(true)}
                      className="px-5 py-2 rounded-lg border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50"
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

      <SettingsModal />
      <SaveProfileModal />
    </div>
  );
}
