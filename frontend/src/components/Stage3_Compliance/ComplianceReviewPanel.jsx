import { useState, useCallback } from "react";
import ChipSelector from "../common/ChipSelector.jsx";
import { api } from "../../api/client.js";

// ─── Framework catalogue shown to the user ──────────────────────────────────
const ALL_FRAMEWORKS = [
  {
    id: "PII",
    label: "PII",
    icon: "👤",
    color: "border-red-300 bg-red-50 text-red-800",
    selectedColor: "border-red-500 bg-red-100 ring-2 ring-red-400",
    desc: "Personally Identifiable Information — names, emails, addresses, SSNs, dates of birth",
  },
  {
    id: "PCI",
    label: "PCI DSS",
    icon: "💳",
    color: "border-orange-300 bg-orange-50 text-orange-800",
    selectedColor: "border-orange-500 bg-orange-100 ring-2 ring-orange-400",
    desc: "Payment Card Industry — card numbers, CVV, bank accounts, IBANs",
  },
  {
    id: "HIPAA",
    label: "HIPAA",
    icon: "🏥",
    color: "border-purple-300 bg-purple-50 text-purple-800",
    selectedColor: "border-purple-500 bg-purple-100 ring-2 ring-purple-400",
    desc: "Health data — medical records, diagnoses, prescriptions, patient IDs",
  },
  {
    id: "GDPR",
    label: "GDPR",
    icon: "🇪🇺",
    color: "border-blue-300 bg-blue-50 text-blue-800",
    selectedColor: "border-blue-500 bg-blue-100 ring-2 ring-blue-400",
    desc: "EU/EEA personal data — any data that can identify EU residents",
  },
  {
    id: "CCPA",
    label: "CCPA",
    icon: "🔵",
    color: "border-cyan-300 bg-cyan-50 text-cyan-800",
    selectedColor: "border-cyan-500 bg-cyan-100 ring-2 ring-cyan-400",
    desc: "California Consumer Privacy Act — personal data of California residents",
  },
  {
    id: "SOX",
    label: "SOX",
    icon: "📊",
    color: "border-yellow-300 bg-yellow-50 text-yellow-800",
    selectedColor: "border-yellow-500 bg-yellow-100 ring-2 ring-yellow-400",
    desc: "Sarbanes-Oxley — financial records, compensation, audit trails",
  },
  {
    id: "FERPA",
    label: "FERPA",
    icon: "🎓",
    color: "border-green-300 bg-green-50 text-green-800",
    selectedColor: "border-green-500 bg-green-100 ring-2 ring-green-400",
    desc: "Education records — student IDs, grades, transcripts, enrollment",
  },
];

const FW_BADGE_COLOR = {
  PII:   "bg-red-100 text-red-700",
  PCI:   "bg-orange-100 text-orange-700",
  HIPAA: "bg-purple-100 text-purple-700",
  GDPR:  "bg-blue-100 text-blue-700",
  CCPA:  "bg-cyan-100 text-cyan-700",
  SOX:   "bg-yellow-100 text-yellow-800",
  FERPA: "bg-green-100 text-green-700",
};

const MASKING_ACTIONS = [
  { id: "fake_realistic",    label: "Fake realistic" },
  { id: "format_preserving", label: "Format-preserving fake" },
  { id: "mask",              label: "Mask with ***" },
  { id: "redact",            label: "Redact entirely" },
];

const findAction = (val) => MASKING_ACTIONS.find((a) => a.id === val || a.label === val);
const labelFor   = (val) => findAction(val)?.label ?? val;

// ─── Framework selector card ────────────────────────────────────────────────
function FrameworkCard({ fw, selected, inferred, onToggle }) {
  const meta = ALL_FRAMEWORKS.find((f) => f.id === fw.id || f.id === fw) || {
    id: fw.id || fw, label: fw.id || fw, icon: "⚠️",
    color: "border-gray-300 bg-gray-50 text-gray-800",
    selectedColor: "border-gray-500 bg-gray-100 ring-2 ring-gray-400",
    desc: "",
  };

  return (
    <button
      type="button"
      onClick={() => onToggle(meta.id)}
      className={[
        "relative text-left rounded-xl border-2 p-3 transition cursor-pointer w-full",
        selected ? meta.selectedColor : meta.color,
      ].join(" ")}
    >
      {inferred && (
        <span className="absolute top-2 right-2 text-xs bg-white/70 px-1.5 py-0.5 rounded-full text-gray-500">
          detected
        </span>
      )}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{meta.icon}</span>
        <span className="font-semibold text-sm">{meta.label}</span>
        {selected && <span className="ml-auto text-green-600 text-sm">✓</span>}
      </div>
      <p className="text-xs opacity-75 leading-snug">{meta.desc}</p>
    </button>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────
export default function ComplianceReviewPanel({
  schema,
  complianceRules,
  onUpdate,
  detectedFrameworks = [],
  selectedFrameworks,
  onFrameworksChange,
  onBack,
  onContinue,
}) {
  const [step, setStep] = useState("select");            // "select" | "fields"
  const [normalizingFields, setNormalizingFields] = useState({}); // fieldName → true while pending
  const [ruleWarnings, setRuleWarnings] = useState({});           // fieldName → warning string

  // ── Step 1: Framework selection ──────────────────────────────────────────
  const toggleFramework = (id) => {
    const next = selectedFrameworks.includes(id)
      ? selectedFrameworks.filter((f) => f !== id)
      : [...selectedFrameworks, id];
    onFrameworksChange(next);
  };

  const knownIds     = ALL_FRAMEWORKS.map((f) => f.id);
  const customFws    = selectedFrameworks.filter((f) => !knownIds.includes(f));
  const noneSelected = selectedFrameworks.length === 0;

  // ── Step 2: Filtered field handling ─────────────────────────────────────
  // Only show fields whose detected frameworks overlap with the user's selection
  const allSensitiveFields = [];
  const autoFields = [];

  for (const t of schema?.tables || []) {
    for (const c of t.columns) {
      const compliance = c.pii || {};
      if (!compliance.is_sensitive && !compliance.is_pii) continue;

      const fieldFws = compliance.frameworks || [];
      const overlaps = selectedFrameworks.some((f) => fieldFws.includes(f));
      const isCustomInContext = !!complianceRules[c.name]?.custom_rule;
      const hasNonTrivialDefault = compliance.default_action && compliance.default_action !== "fake_realistic";
      // Also check the action already stored in complianceRules (e.g. from demo templates or saved profiles)
      const storedAction = complianceRules[c.name]?.action;
      const hasNonTrivialStoredAction = !!(storedAction && storedAction !== "fake_realistic");

      if (overlaps && (isCustomInContext || hasNonTrivialDefault || hasNonTrivialStoredAction)) {
        allSensitiveFields.push({ table: t.table_name, col: c, compliance });
      } else if (overlaps) {
        autoFields.push({ table: t.table_name, col: c, compliance });
      }
      // Fields with no overlap are completely silent — not listed at all
    }
  }

  const applyDefaults = () => {
    const next = { ...complianceRules };
    for (const { col, compliance } of allSensitiveFields) {
      if (!next[col.name]) {
        next[col.name] = {
          action: compliance.default_action || "fake_realistic",
          custom_rule: null,
          frameworks: compliance.frameworks || [],
        };
      }
    }
    onUpdate(next);
  };

  const updateField = useCallback(async (fieldName, patch) => {
    // Immediately apply the visible update so the UI feels instant
    const next = {
      ...complianceRules,
      [fieldName]: { ...(complianceRules[fieldName] || {}), ...patch },
    };
    onUpdate(next);

    // Clear any stale warning whenever the field is touched
    setRuleWarnings((prev) => {
      if (!prev[fieldName]) return prev;
      const copy = { ...prev };
      delete copy[fieldName];
      return copy;
    });

    // If this is a custom rule text, kick off background normalisation
    if (patch.action === "Custom" && patch.custom_rule) {
      setNormalizingFields((prev) => ({ ...prev, [fieldName]: true }));
      try {
        const result = await api.normalizeRule(patch.custom_rule);
        if (result?.masking_op) {
          // Success — store the structured op and clear any warning
          onUpdate((prev) => ({
            ...prev,
            [fieldName]: { ...(prev[fieldName] || {}), masking_op: result.masking_op },
          }));
          setRuleWarnings((prev) => {
            const copy = { ...prev };
            delete copy[fieldName];
            return copy;
          });
        } else {
          // LLM couldn't parse it — surface a helpful hint
          setRuleWarnings((prev) => ({
            ...prev,
            [fieldName]: "Couldn't parse this rule automatically. Try rephrasing as e.g. \"show last 4 digits\", \"mask first 6 chars\", or \"redact\".",
          }));
        }
      } catch (_) {
        // Normalisation failure is non-fatal — keyword fallback runs at generation time
      } finally {
        setNormalizingFields((prev) => {
          const copy = { ...prev };
          delete copy[fieldName];
          return copy;
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [complianceRules, onUpdate]);

  // ── Render: Step 1 — pick frameworks ────────────────────────────────────
  if (step === "select") {
    return (
      <div className="space-y-5">

        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <p className="font-medium mb-1">Which regulations apply to this dataset?</p>
          <p className="text-xs text-amber-600">
            We've pre-selected what we inferred from your description and column names.
            Deselect anything that doesn't apply, or add others.
          </p>
        </div>

        {/* Known framework cards */}
        <div className="grid grid-cols-2 gap-3">
          {ALL_FRAMEWORKS.map((fw) => (
            <FrameworkCard
              key={fw.id}
              fw={fw}
              selected={selectedFrameworks.includes(fw.id)}
              inferred={detectedFrameworks.includes(fw.id)}
              onToggle={toggleFramework}
            />
          ))}
        </div>

        {/* Custom / unlisted framework */}
        <div>
          <p className="text-xs text-gray-500 mb-2">Other regulation not listed above?</p>
          <ChipSelector
            options={[]}
            value={customFws}
            onChange={(vals) => {
              const standardIds = selectedFrameworks.filter((f) => knownIds.includes(f));
              onFrameworksChange([...standardIds, ...(Array.isArray(vals) ? vals : [vals])]);
            }}
            allowCustom
            multi
            customPlaceholder="Type regulation name, e.g. PIPEDA, LGPD..."
          />
        </div>

        {/* None apply */}
        <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
          <input
            type="checkbox"
            checked={noneSelected}
            onChange={() => onFrameworksChange(noneSelected ? detectedFrameworks : [])}
            className="rounded"
          />
          None of these apply — generate without compliance restrictions
        </label>

        {/* Navigation */}
        <div className="flex justify-between pt-2">
          <button onClick={onBack} className="px-5 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">
            Back
          </button>
          <button
            onClick={() => noneSelected ? onContinue?.() : setStep("fields")}
            className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 text-sm"
          >
            {noneSelected ? "Continue without restrictions" : `Review ${selectedFrameworks.length} framework${selectedFrameworks.length !== 1 ? "s" : ""} →`}
          </button>
        </div>
      </div>
    );
  }

  // ── Render: Step 2 — field-level handling ────────────────────────────────
  return (
    <div className="space-y-4">

      {/* Header with selected frameworks + back link */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex flex-wrap gap-1.5">
          {selectedFrameworks.map((fw) => {
            const meta = ALL_FRAMEWORKS.find((f) => f.id === fw);
            return (
              <span key={fw} className={`text-xs px-2 py-0.5 rounded-full font-medium ${FW_BADGE_COLOR[fw] || "bg-gray-100 text-gray-700"}`}>
                {meta?.icon} {fw}
              </span>
            );
          })}
        </div>
        <button
          onClick={() => setStep("select")}
          className="text-xs text-indigo-600 hover:underline"
        >
          ← Change frameworks
        </button>
      </div>

      {/* No fields require decisions */}
      {allSensitiveFields.length === 0 && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800">
          <p className="font-medium">✓ No decisions needed — all fields will be auto-handled</p>
          <p className="text-xs text-green-600 mt-1">
            Every sensitive field under your selected frameworks will be generated with realistic synthetic values.
            No masking or redaction is required for this dataset.
          </p>
        </div>
      )}

      {/* Fields needing explicit decisions */}
      {allSensitiveFields.length > 0 && (
        <>
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-600">
              {allSensitiveFields.length} field{allSensitiveFields.length !== 1 ? "s" : ""} need your input
            </p>
            <button
              onClick={applyDefaults}
              className="text-sm px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
            >
              Apply recommended defaults
            </button>
          </div>

          {allSensitiveFields.map(({ col, compliance }) => {
            const rule            = complianceRules[col.name] || {};
            const preFilledCtx    = !!rule.custom_rule;
            const isCustom        = rule.action === "Custom" || (rule.action && !findAction(rule.action));
            const chipValue       = isCustom
              ? (rule.custom_rule || rule.action)
              : labelFor(rule.action || compliance.default_action);
            const fieldFws        = compliance.frameworks || [];

            return (
              <div key={col.name} className="border border-gray-200 rounded-xl p-4 space-y-3">
                <div className="flex items-start gap-2 flex-wrap">
                  <span className="font-semibold text-gray-900">{col.name}</span>
                  <span className="text-xs text-gray-400">({compliance.field_type || col.type})</span>
                  {preFilledCtx && (
                    <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">
                      ✓ pre-filled from description
                    </span>
                  )}
                  <div className="flex flex-wrap gap-1 ml-auto">
                    {fieldFws.filter((f) => selectedFrameworks.includes(f)).map((fw) => (
                      <span key={fw} className={`text-xs px-2 py-0.5 rounded-full font-medium ${FW_BADGE_COLOR[fw] || "bg-gray-100 text-gray-700"}`}>
                        {fw}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">How should this field be handled in generated data?</p>
                  <ChipSelector
                    options={MASKING_ACTIONS.map((a) => a.label)}
                    value={chipValue}
                    onChange={(lbl) => {
                      const matched = findAction(lbl);
                      updateField(col.name, matched
                        ? { action: matched.id, custom_rule: null, frameworks: fieldFws }
                        : { action: "Custom", custom_rule: lbl, frameworks: fieldFws }
                      );
                    }}
                    allowCustom
                    customPlaceholder="Describe how to handle this field..."
                  />
                </div>

                {rule.custom_rule && (
                  <div className="space-y-1.5">
                    <div className="text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-2">
                      <span className="text-amber-800 flex-1">📋 {rule.custom_rule}</span>
                      {normalizingFields[col.name] ? (
                        <span className="text-amber-500 whitespace-nowrap animate-pulse">⚙ parsing…</span>
                      ) : rule.masking_op ? (
                        <span
                          className="text-green-600 whitespace-nowrap"
                          title={`Op: ${rule.masking_op.type}${rule.masking_op.n != null ? `, n=${rule.masking_op.n}` : ""}`}
                        >
                          ✓ structured
                        </span>
                      ) : null}
                    </div>
                    {ruleWarnings[col.name] && (
                      <div className="text-xs bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex items-start gap-1.5 text-red-700">
                        <span className="mt-0.5 shrink-0">⚠️</span>
                        <span>{ruleWarnings[col.name]}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}

      {/* Auto-handled fields under selected frameworks */}
      {autoFields.length > 0 && (
        <div className={`rounded-xl border p-4 space-y-2 ${allSensitiveFields.length === 0 ? "border-green-200 bg-green-50" : "border-gray-100 bg-gray-50"}`}>
          <p className={`text-xs font-medium ${allSensitiveFields.length === 0 ? "text-green-700" : "text-gray-500"}`}>
            {autoFields.length} field{autoFields.length !== 1 ? "s" : ""} — auto-generated with realistic synthetic values
          </p>
          <div className="flex flex-wrap gap-2">
            {autoFields.map(({ col, compliance }) => {
              const fieldFws = (compliance.frameworks || []).filter(f => selectedFrameworks.includes(f));
              return (
                <span key={col.name} className="inline-flex items-center gap-1 text-xs bg-white border border-gray-200 rounded-full px-2.5 py-1 text-gray-600 font-mono">
                  {col.name}
                  {fieldFws.map(fw => (
                    <span key={fw} className={`text-xs px-1.5 py-0.5 rounded-full font-sans font-medium ${FW_BADGE_COLOR[fw] || "bg-gray-100 text-gray-600"}`}>
                      {fw}
                    </span>
                  ))}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-2">
        <button onClick={() => setStep("select")} className="px-5 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">
          Back
        </button>
        <button onClick={onContinue} className="px-5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
          Continue
        </button>
      </div>
    </div>
  );
}
