/**
 * Shows the user what was understood from their natural language input.
 * For multi-table schemas the summary is grouped per entity/table.
 * Only surfaces things worth calling out — distributions, special masking rules, temporal.
 * "Fake realistic" is the default for everything, so we never mention it.
 */

const ACTION_LABELS = {
  mask:              "Masked",
  redact:            "Redacted",
  format_preserving: "Format-preserving fake",
};

function ColPill({ name }) {
  return (
    <span className="inline-block bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded text-xs font-mono mr-1 mb-0.5">
      {name}
    </span>
  );
}

function BulletRow({ children }) {
  return (
    <li className="flex items-start gap-2">
      <span className="text-indigo-400 mt-0.5 shrink-0">•</span>
      <span>{children}</span>
    </li>
  );
}

/** Renders the bullets that are relevant to a specific set of column names. */
function TableSummaryRows({ columns, colNames, distributions, meaningfulRules, temporal }) {
  const hasColumns     = columns.length > 0;
  const tableDists     = Object.entries(distributions  || {}).filter(([k]) => colNames.has(k));
  const tableRules     = meaningfulRules.filter(([k])  => colNames.has(k));
  const tableTemporal  = Object.entries(temporal       || {}).filter(([k]) => colNames.has(k));

  const hasAnything = hasColumns || tableDists.length || tableRules.length || tableTemporal.length;
  if (!hasAnything) return null;

  return (
    <ul className="space-y-1.5 text-sm text-indigo-900">

      {hasColumns && (
        <BulletRow>
          <span className="font-medium">Columns:</span>{" "}
          {columns.map((c) => <ColPill key={c.name} name={c.name} />)}
        </BulletRow>
      )}

      {tableDists.map(([col, vals]) => (
        <BulletRow key={col}>
          <span className="font-medium capitalize">{col} mix:</span>{" "}
          {Object.entries(vals).map(([val, pct]) => (
            <span key={val} className="mr-2">{val} {pct}%</span>
          ))}
        </BulletRow>
      ))}

      {tableRules.map(([col, rule]) => (
        <BulletRow key={col}>
          <span className="font-medium capitalize">{col}</span>{" "}
          →{" "}
          {rule.custom_rule
            ? <span className="italic">{rule.custom_rule}</span>
            : <span>{ACTION_LABELS[rule.action] || rule.action}</span>
          }
        </BulletRow>
      ))}

      {tableTemporal.map(([col, t]) => (
        <BulletRow key={col}>
          <span className="font-medium capitalize">{col}</span>{" "}
          → {t.description || `aged ${t.aging_days} days`}
        </BulletRow>
      ))}

    </ul>
  );
}

export default function UnderstandingSummary({ extracted, schema }) {
  if (!extracted) return null;

  const { volume, distributions, compliance_rules, temporal } = extracted;
  const raw_et     = extracted.entity_type;
  const entity_type = (raw_et && String(raw_et).trim().toLowerCase() !== "null") ? raw_et : null;

  const normalize = (s) => (s || "").toLowerCase().replace(/[\s-]+/g, "_");
  const meaningfulRules = Object.entries(compliance_rules || {}).filter(([, rule]) => {
    const action = normalize(rule.action);
    return rule.custom_rule || (action && action !== "fake_realistic");
  });

  const tables = schema?.tables || [];

  // Nothing interesting to show across all tables — skip the card
  const hasDistributions      = distributions  && Object.keys(distributions).length  > 0;
  const hasMeaningfulCompliance = meaningfulRules.length > 0;
  const hasTemporal           = temporal       && Object.keys(temporal).length       > 0;
  const hasColumns            = tables.some((t) => t.columns?.length > 0);

  if (!volume && !entity_type && !hasDistributions && !hasMeaningfulCompliance && !hasTemporal && !hasColumns) {
    return null;
  }

  // ── Single-table: flat summary (original layout) ─────────────────────────
  if (tables.length <= 1) {
    const columns = tables[0]?.columns || [];
    const colNames = new Set(columns.map((c) => c.name));

    return (
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-indigo-600 text-lg">🧠</span>
          <h3 className="text-sm font-semibold text-indigo-800">Here's what I understood from your description</h3>
        </div>

        <ul className="space-y-1.5 text-sm text-indigo-900">
          {(entity_type || volume) && (
            <BulletRow>
              <span className="font-medium">Entity:</span>{" "}
              {entity_type && <span className="capitalize">{entity_type}</span>}
              {volume && <span> — <span className="font-medium">{volume.toLocaleString()} records</span></span>}
            </BulletRow>
          )}

          <TableSummaryRows
            columns={columns}
            colNames={colNames}
            distributions={distributions}
            meaningfulRules={meaningfulRules}
            temporal={temporal}
          />
        </ul>

        <p className="text-xs text-indigo-500 mt-3">
          Pre-filled below based on your description — adjust anything that doesn't look right.
        </p>
      </div>
    );
  }

  // ── Multi-table: group by entity ─────────────────────────────────────────
  return (
    <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-indigo-600 text-lg">🧠</span>
        <h3 className="text-sm font-semibold text-indigo-800">Here's what I understood from your description</h3>
      </div>

      {/* Top-level: overall volume / root entity */}
      {(entity_type || volume) && (
        <p className="text-sm text-indigo-900 mb-3">
          {entity_type && <span className="font-medium capitalize">{entity_type}</span>}
          {volume && (
            <span> — <span className="font-medium">{volume.toLocaleString()} records</span></span>
          )}
        </p>
      )}

      {/* Per-entity sections */}
      <div className="space-y-3">
        {tables.map((table, idx) => {
          const colNames = new Set(table.columns.map((c) => c.name));
          const tableDists    = Object.entries(distributions  || {}).filter(([k]) => colNames.has(k));
          const tableRules    = meaningfulRules.filter(([k])  => colNames.has(k));
          const tableTemporal = Object.entries(temporal       || {}).filter(([k]) => colNames.has(k));

          const hasAnything = table.columns.length || tableDists.length || tableRules.length || tableTemporal.length;
          if (!hasAnything) return null;

          return (
            <div
              key={table.table_name}
              className={`${idx > 0 ? "pt-3 border-t border-indigo-200" : ""}`}
            >
              <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wide mb-1.5">
                {table.table_name}
              </p>
              <TableSummaryRows
                columns={table.columns}
                colNames={colNames}
                distributions={distributions}
                meaningfulRules={meaningfulRules}
                temporal={temporal}
              />
            </div>
          );
        })}
      </div>

      <p className="text-xs text-indigo-500 mt-3">
        Pre-filled below based on your description — adjust anything that doesn't look right.
      </p>
    </div>
  );
}
