import ChipSelector from "../common/ChipSelector.jsx";

const ACTIONS = [
  { id: "fake_realistic",    label: "Fake realistic" },
  { id: "format_preserving", label: "Format-preserving fake" },
  { id: "mask",              label: "Mask with ***" },
  { id: "redact",            label: "Redact" },
];

// Accept both id ("fake_realistic") and label ("Fake realistic") when matching
const findAction = (val) =>
  ACTIONS.find((a) => a.id === val || a.label === val);

const labelFor = (val) => findAction(val)?.label ?? val;
const idFor    = (val) => findAction(val)?.id    ?? val;

export default function PIIReviewPanel({ schema, complianceRules, onUpdate }) {
  const piiFields = [];
  for (const t of schema?.tables || []) {
    for (const c of t.columns) {
      if (c.pii?.is_pii) piiFields.push({ table: t.table_name, col: c });
    }
  }

  const updateField = (fieldName, patch) => {
    onUpdate({ ...complianceRules, [fieldName]: { ...(complianceRules[fieldName] || {}), ...patch } });
  };

  const applyAll = () => {
    const next = { ...complianceRules };
    for (const { col } of piiFields) {
      if (!next[col.name]) next[col.name] = { action: "fake_realistic", custom_rule: null };
    }
    onUpdate(next);
  };

  if (piiFields.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4 text-center">
        No PII fields detected in the schema.
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-gray-600">{piiFields.length} sensitive field(s) detected</p>
        <button
          onClick={applyAll}
          className="text-sm px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
        >
          Apply all recommendations
        </button>
      </div>

      <div className="space-y-3">
        {piiFields.map(({ table, col }) => {
          const rule = complianceRules[col.name] || {};
          const preFilledFromContext = !!rule.action;
          const isCustomAction = rule.action === "Custom" || (rule.action && !findAction(rule.action));
          const chipValue = isCustomAction ? (rule.custom_rule || rule.action) : labelFor(rule.action);

          return (
            <div key={`${table}.${col.name}`} className="border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{col.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">
                    {col.pii.category}
                  </span>
                  <span className="text-xs text-gray-400">{col.pii.pii_type}</span>
                  {preFilledFromContext && (
                    <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">
                      from your description
                    </span>
                  )}
                </div>
              </div>

              <ChipSelector
                options={ACTIONS.map((a) => a.label)}
                value={chipValue}
                onChange={(lbl) => {
                  const matched = findAction(lbl);
                  if (matched) {
                    updateField(col.name, { action: matched.id, custom_rule: null });
                  } else {
                    // Free-form custom rule entered directly
                    updateField(col.name, { action: "Custom", custom_rule: lbl });
                  }
                }}
                allowCustom
                customPlaceholder="Describe masking rule..."
              />

              {/* Show custom rule description if set */}
              {rule.custom_rule && (
                <p className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                  📋 {rule.custom_rule}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
