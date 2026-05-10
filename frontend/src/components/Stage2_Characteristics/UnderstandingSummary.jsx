/**
 * Shows the user what was understood from their natural language input.
 * Only surfaces things worth calling out — distributions, special masking rules, temporal.
 * "Fake realistic" is the default for everything, so we never mention it.
 */

const ACTION_LABELS = {
  mask:              "Masked",
  redact:            "Redacted",
  format_preserving: "Format-preserving fake",
};

export default function UnderstandingSummary({ extracted, schema }) {
  if (!extracted) return null;

  const { volume, distributions, compliance_rules, temporal } = extracted;
  // Guard against LLMs returning the string "null" instead of a real entity name
  const raw_et = extracted.entity_type;
  const entity_type = (raw_et && String(raw_et).trim().toLowerCase() !== "null") ? raw_et : null;

  const columns = schema?.tables?.[0]?.columns || [];

  // Only show compliance entries that have something non-trivial to say.
  // Normalize action to lowercase+underscore so "Fake realistic" == "fake_realistic".
  const normalize = (s) => (s || "").toLowerCase().replace(/[\s-]+/g, "_");
  const meaningfulRules = Object.entries(compliance_rules || {}).filter(([, rule]) => {
    const action = normalize(rule.action);
    return rule.custom_rule || (action && action !== "fake_realistic");
  });

  const hasDistributions = distributions && Object.keys(distributions).length > 0;
  const hasMeaningfulCompliance = meaningfulRules.length > 0;
  const hasTemporal = temporal && Object.keys(temporal).length > 0;

  // Nothing interesting to show — skip the card entirely
  if (!volume && !entity_type && !hasDistributions && !hasMeaningfulCompliance && !hasTemporal && columns.length === 0) {
    return null;
  }

  return (
    <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-indigo-600 text-lg">🧠</span>
        <h3 className="text-sm font-semibold text-indigo-800">Here's what I understood from your description</h3>
      </div>

      <ul className="space-y-1.5 text-sm text-indigo-900">

        {/* Entity + volume */}
        {(entity_type || volume) && (
          <li className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">•</span>
            <span>
              <span className="font-medium">Entity:</span>{" "}
              {entity_type && <span className="capitalize">{entity_type}</span>}
              {volume && <span> — <span className="font-medium">{volume.toLocaleString()} records</span></span>}
            </span>
          </li>
        )}

        {/* Columns */}
        {columns.length > 0 && (
          <li className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">•</span>
            <span>
              <span className="font-medium">Columns:</span>{" "}
              {columns.map((c) => (
                <span
                  key={c.name}
                  className="inline-block bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded text-xs font-mono mr-1 mb-0.5"
                >
                  {c.name}
                </span>
              ))}
            </span>
          </li>
        )}

        {/* Distributions — only where something was specified */}
        {hasDistributions && Object.entries(distributions).map(([col, vals]) => (
          <li key={col} className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">•</span>
            <span>
              <span className="font-medium capitalize">{col} mix:</span>{" "}
              {Object.entries(vals).map(([val, pct]) => (
                <span key={val} className="mr-2">{val} {pct}%</span>
              ))}
            </span>
          </li>
        ))}

        {/* Compliance — only non-trivial rules (masking, redaction, custom) */}
        {hasMeaningfulCompliance && meaningfulRules.map(([col, rule]) => (
          <li key={col} className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">•</span>
            <span>
              <span className="font-medium capitalize">{col}</span>{" "}
              →{" "}
              {rule.custom_rule
                ? <span className="italic">{rule.custom_rule}</span>
                : <span>{ACTION_LABELS[rule.action] || rule.action}</span>
              }
            </span>
          </li>
        ))}

        {/* Temporal */}
        {hasTemporal && Object.entries(temporal).map(([col, t]) => (
          <li key={col} className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">•</span>
            <span>
              <span className="font-medium capitalize">{col}</span>{" "}
              → {t.description || `aged ${t.aging_days} days`}
            </span>
          </li>
        ))}

      </ul>

      <p className="text-xs text-indigo-500 mt-3">
        Pre-filled below based on your description — adjust anything that doesn't look right.
      </p>
    </div>
  );
}
