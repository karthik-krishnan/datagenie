import { useState } from "react";
import ChipSelector from "../common/ChipSelector.jsx";

// ── Colour palette for enum values (inline styles — safe from Tailwind purge) ─
const PALETTE = [
  "#6366f1", // indigo
  "#8b5cf6", // violet
  "#0ea5e9", // sky
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#f97316", // orange
  "#14b8a6", // teal
  "#ec4899", // pink
  "#64748b", // slate
];

// ── Helpers ────────────────────────────────────────────────────────────────────
const RANGE_TYPES      = new Set(["integer", "float"]);
const CATEGORICAL_TYPE = "string";
const SKIP_TYPES       = new Set(["email", "phone", "uuid", "date", "boolean"]);

function pctDisplay(raw) {
  if (raw === undefined || raw === null || raw === "") return "";
  return Math.round(parseFloat(raw) * 100);
}

// Count how many distribution/range controls have been explicitly set for a table
function countConfigured(table, characteristics) {
  let n = 0;
  for (const col of table.columns) {
    const key = `${table.table_name}.${col.name}`;
    if (col.type === "enum" && col.enum_values?.length) {
      const dist = characteristics.distributions[key] || {};
      if (Object.keys(dist).length > 0) n++;
    } else if (col.type === "date") {
      if (characteristics.temporal[key]) n++;
    } else if (col.type === "boolean") {
      const dist = characteristics.distributions[key];
      if (dist && dist.true_ratio !== undefined && dist.true_ratio !== 0.5) n++;
    } else if (RANGE_TYPES.has(col.type)) {
      if ((characteristics.ranges || {})[key]) n++;
    }
  }
  return n;
}

// ── Visual enum distribution control ──────────────────────────────────────────
function EnumDistributionControl({ tableName, col, current, onChange }) {
  const vals  = col.enum_values;
  const total = vals.reduce((s, v) => s + (parseFloat(current[v]) || 0), 0);

  return (
    <div className="space-y-2.5">
      {/* Stacked proportion bar */}
      <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-100">
        {total > 0
          ? vals.map((v, i) => {
              const w = ((parseFloat(current[v]) || 0) / total) * 100;
              return (
                <div
                  key={v}
                  style={{ width: `${w}%`, backgroundColor: PALETTE[i % PALETTE.length], transition: "width 0.2s" }}
                />
              );
            })
          : <div className="flex-1 bg-gray-200 rounded-full" />
        }
      </div>

      {/* Editable chips */}
      <div className="flex flex-wrap gap-2">
        {vals.map((v, i) => {
          const pct = current[v] !== undefined ? Math.round(current[v] * 100) : "";
          return (
            <label
              key={v}
              className="flex items-center gap-1.5 border border-gray-200 rounded-full pl-2.5 pr-3 py-1 bg-white hover:border-indigo-300 cursor-text transition-colors"
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
              />
              <span className="text-sm text-gray-700 select-none">{v}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={pct}
                onChange={(e) => {
                  const n = parseInt(e.target.value || "0", 10);
                  onChange({ ...current, [v]: n / 100 });
                }}
                placeholder="0"
                className="w-9 text-sm text-right outline-none bg-transparent font-semibold text-indigo-600"
              />
              <span className="text-xs text-gray-400 select-none">%</span>
            </label>
          );
        })}
      </div>

      {total > 0 && Math.round(total * 100) !== 100 && (
        <p className="text-xs text-amber-600">Total {Math.round(total * 100)}% — will be normalised at generation time</p>
      )}
    </div>
  );
}

// ── Visual boolean control ─────────────────────────────────────────────────────
function BooleanControl({ tableName, col, current, onChange }) {
  const trueRatio  = current?.true_ratio ?? 0.5;
  const truePct    = Math.round(trueRatio * 100);
  const falsePct   = 100 - truePct;

  return (
    <div className="space-y-2.5">
      {/* Stacked bar */}
      <div className="flex h-1.5 rounded-full overflow-hidden">
        <div style={{ width: `${truePct}%`, backgroundColor: PALETTE[3], transition: "width 0.2s" }} />
        <div style={{ width: `${falsePct}%`, backgroundColor: "#e5e7eb" }} />
      </div>

      {/* True / False chips */}
      <div className="flex gap-2">
        {[
          { label: "True",  ratio: trueRatio,      color: PALETTE[3] },
          { label: "False", ratio: 1 - trueRatio,  color: "#9ca3af"  },
        ].map(({ label, ratio, color }) => (
          <label
            key={label}
            className="flex items-center gap-1.5 border border-gray-200 rounded-full pl-2.5 pr-3 py-1 bg-white hover:border-indigo-300 cursor-text transition-colors"
          >
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            <span className="text-sm text-gray-700 select-none">{label}</span>
            <input
              type="number"
              min={0}
              max={100}
              value={Math.round(ratio * 100)}
              onChange={(e) => {
                const n = Math.max(0, Math.min(100, parseInt(e.target.value || "0", 10)));
                const newTrue = label === "True" ? n / 100 : 1 - n / 100;
                onChange({ true_ratio: Math.max(0, Math.min(1, newTrue)) });
              }}
              className="w-9 text-sm text-right outline-none bg-transparent font-semibold text-indigo-600"
            />
            <span className="text-xs text-gray-400 select-none">%</span>
          </label>
        ))}
      </div>
    </div>
  );
}

// ── Inline categorical distributor (for unconfigured string / enum-no-values) ─
function ConfigureDistribution({ onSave, onCancel }) {
  const [rows, setRows] = useState([{ value: "", pct: "" }, { value: "", pct: "" }]);

  const updateRow = (i, field, val) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, [field]: val } : r)));
  const addRow    = () => setRows((prev) => [...prev, { value: "", pct: "" }]);
  const removeRow = (i) => setRows((prev) => prev.filter((_, idx) => idx !== i));

  const total = rows.reduce((s, r) => s + (parseInt(r.pct, 10) || 0), 0);
  const valid = rows.filter((r) => r.value.trim() && r.pct !== "").length >= 2;

  const handleSave = () => {
    const filled = rows.filter((r) => r.value.trim() && r.pct !== "");
    const values = filled.map((r) => r.value.trim());
    const dist   = {};
    filled.forEach((r) => { dist[r.value.trim()] = parseInt(r.pct, 10) / 100; });
    onSave(values, dist);
  };

  return (
    <div className="mt-2 border border-dashed border-indigo-300 rounded-lg p-3 bg-indigo-50/30 space-y-3">
      <p className="text-xs text-gray-500">Add values and their percentage share. Doesn't need to sum to 100% — the generator will normalise.</p>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2">
            <input value={r.value} onChange={(e) => updateRow(i, "value", e.target.value)}
              placeholder="Value"
              className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm outline-none focus:border-indigo-400" />
            <input type="number" min={0} max={100} value={r.pct}
              onChange={(e) => updateRow(i, "pct", e.target.value)} placeholder="%"
              className="w-16 border border-gray-300 rounded px-2 py-1 text-sm outline-none focus:border-indigo-400" />
            <span className="text-xs text-gray-400">%</span>
            {rows.length > 2 && (
              <button onClick={() => removeRow(i)} className="text-gray-300 hover:text-red-400 text-base leading-none">✕</button>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={addRow} className="text-xs text-indigo-600 hover:text-indigo-800">+ Add value</button>
          {total > 0 && (
            <span className={`text-xs ${total === 100 ? "text-green-600" : "text-amber-600"}`}>
              Total: {total}%{total !== 100 ? " (will be normalised)" : " ✓"}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 border border-gray-200 rounded">Cancel</button>
          <button onClick={handleSave} disabled={!valid}
            className="text-xs bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700 disabled:opacity-40">
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Inline range configurator for numeric columns ──────────────────────────────
function ConfigureRange({ colType, currentRange, onSave, onCancel }) {
  const [min, setMin] = useState(currentRange?.min ?? "");
  const [max, setMax] = useState(currentRange?.max ?? "");
  const isFloat = colType === "float";
  const minN    = isFloat ? parseFloat(min) : parseInt(min, 10);
  const maxN    = isFloat ? parseFloat(max) : parseInt(max, 10);
  const valid   = min !== "" && max !== "" && !isNaN(minN) && !isNaN(maxN) && minN <= maxN;

  return (
    <div className="mt-2 border border-dashed border-indigo-300 rounded-lg p-3 bg-indigo-50/30 space-y-3">
      <p className="text-xs text-gray-500">
        Set the {isFloat ? "decimal" : "integer"} range. Random values will be drawn between min and max.
      </p>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 w-7">Min</label>
          <input type="number" step={isFloat ? "0.01" : "1"} value={min}
            onChange={(e) => setMin(e.target.value)} placeholder={isFloat ? "0.0" : "0"}
            className="w-28 border border-gray-300 rounded px-2 py-1 text-sm outline-none focus:border-indigo-400" />
        </div>
        <span className="text-gray-400">–</span>
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 w-7">Max</label>
          <input type="number" step={isFloat ? "0.01" : "1"} value={max}
            onChange={(e) => setMax(e.target.value)} placeholder={isFloat ? "100.0" : "1000"}
            className="w-28 border border-gray-300 rounded px-2 py-1 text-sm outline-none focus:border-indigo-400" />
        </div>
        {min !== "" && max !== "" && !isNaN(minN) && !isNaN(maxN) && minN > maxN && (
          <span className="text-xs text-red-500">Min must be ≤ Max</span>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 border border-gray-200 rounded">Cancel</button>
        <button onClick={() => onSave({ min: minN, max: maxN })} disabled={!valid}
          className="text-xs bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700 disabled:opacity-40">
          Save
        </button>
      </div>
    </div>
  );
}

// ── Per-table panel ────────────────────────────────────────────────────────────
function TablePanel({ table, tableIndex, characteristics, configuring, setConfiguring, onUpdate, onSchemaUpdate }) {
  const tname = table.table_name;

  const setDistribution = (colName, dist) => {
    const key = `${tname}.${colName}`;
    onUpdate({ distributions: { ...characteristics.distributions, [key]: dist } });
  };

  const setRange = (colName, range) => {
    const key = `${tname}.${colName}`;
    onUpdate({ ranges: { ...(characteristics.ranges || {}), [key]: range } });
  };

  const setTemporal = (colName, days) => {
    const key = `${tname}.${colName}`;
    onUpdate({ temporal: { ...characteristics.temporal, [key]: { days_back: days } } });
  };

  const configured = new Set();

  // ── Configured column controls ──────────────────────────────────────────────
  const configuredControls = table.columns.map((col) => {
    const distKey = `${tname}.${col.name}`;

    if (col.type === "enum" && col.enum_values?.length) {
      configured.add(col.name);
      const current = characteristics.distributions[distKey] || {};
      return (
        <div key={col.name} className="space-y-1.5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{col.name}</p>
          <EnumDistributionControl
            tableName={tname}
            col={col}
            current={current}
            onChange={(dist) => setDistribution(col.name, dist)}
          />
        </div>
      );
    }

    if (col.type === "boolean") {
      configured.add(col.name);
      const current = characteristics.distributions[distKey] || { true_ratio: 0.5 };
      return (
        <div key={col.name} className="space-y-1.5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{col.name}</p>
          <BooleanControl
            tableName={tname}
            col={col}
            current={current}
            onChange={(dist) => setDistribution(col.name, dist)}
          />
        </div>
      );
    }

    if (col.type === "date") {
      configured.add(col.name);
      const current = characteristics.temporal[distKey];
      const days  = current?.days_back;
      const label = days === 30 ? "Last 30 days" : days === 90 ? "Last 90 days" : days === 365 ? "Last year" : days ? `${days} days` : null;
      return (
        <div key={col.name} className="space-y-1.5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{col.name}</p>
          <ChipSelector
            options={["Last 30 days", "Last 90 days", "Last year"]}
            value={label}
            onChange={(opt) => {
              if (opt === "Last 30 days") setTemporal(col.name, 30);
              else if (opt === "Last 90 days") setTemporal(col.name, 90);
              else if (opt === "Last year") setTemporal(col.name, 365);
              else {
                const m = String(opt).match(/(\d+)/);
                if (m) setTemporal(col.name, parseInt(m[1], 10));
              }
            }}
            allowCustom
            customPlaceholder="e.g. 60"
          />
        </div>
      );
    }

    // Numeric with saved range
    if (RANGE_TYPES.has(col.type)) {
      const saved = (characteristics.ranges || {})[distKey];
      if (saved) {
        configured.add(col.name);
        return (
          <div key={col.name} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{col.name}</p>
              <button onClick={() => setConfiguring(`${col.name}__range`)}
                className="text-xs text-indigo-500 hover:text-indigo-700">
                Edit
              </button>
            </div>
            {configuring === `${col.name}__range` ? (
              <ConfigureRange
                colType={col.type}
                currentRange={saved}
                onCancel={() => setConfiguring(null)}
                onSave={(r) => { setRange(col.name, r); setConfiguring(null); }}
              />
            ) : (
              <span className="text-sm text-gray-500">{saved.min} – {saved.max}</span>
            )}
          </div>
        );
      }
    }

    return null;
  });

  // ── Unconfigured columns ────────────────────────────────────────────────────
  const unconfigured = table.columns.filter((col) => {
    if (configured.has(col.name)) return false;
    if (SKIP_TYPES.has(col.type)) return false;
    if (col.type === "enum") return true;
    if (RANGE_TYPES.has(col.type)) return true;
    if (col.type === CATEGORICAL_TYPE) return true;
    return false;
  });

  return (
    <div className="space-y-5 pt-4">
      {configuredControls}

      {unconfigured.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Not configured</p>
          {unconfigured.map((col) => {
            const isNumeric = RANGE_TYPES.has(col.type);
            const cfgKey    = isNumeric ? `${col.name}__range` : col.name;
            return (
              <div key={col.name} className="border-l-2 border-gray-200 pl-3 py-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    <span className="font-medium text-gray-700">{col.name}</span>
                    <span className="ml-2 text-xs text-gray-400 font-mono">{col.type}</span>
                  </span>
                  {configuring !== cfgKey && (
                    <button
                      onClick={() => setConfiguring(cfgKey)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 hover:bg-indigo-50"
                    >
                      + {isNumeric ? "Set range" : "Configure"}
                    </button>
                  )}
                </div>

                {configuring === cfgKey && isNumeric && (
                  <ConfigureRange
                    colType={col.type}
                    currentRange={null}
                    onCancel={() => setConfiguring(null)}
                    onSave={(r) => { setRange(col.name, r); setConfiguring(null); }}
                  />
                )}
                {configuring === cfgKey && !isNumeric && (
                  <ConfigureDistribution
                    onCancel={() => setConfiguring(null)}
                    onSave={(values, dist) => {
                      if (onSchemaUpdate) onSchemaUpdate(tableIndex, col.name, values);
                      setDistribution(col.name, dist);
                      setConfiguring(null);
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {configuredControls.every((c) => c === null) && unconfigured.length === 0 && (
        <p className="text-sm text-gray-400 py-2">No configurable distributions for this table.</p>
      )}
    </div>
  );
}

// ── Main export — tabbed multi-table view ──────────────────────────────────────
export default function AttributeDistribution({ tables, characteristics, onUpdate, onSchemaUpdate }) {
  const [activeTab, setActiveTab]   = useState(0);
  const [configuring, setConfiguring] = useState(null);

  if (!tables || tables.length === 0) return null;

  const safeTab = Math.min(activeTab, tables.length - 1);

  const handleTabChange = (i) => {
    setActiveTab(i);
    setConfiguring(null);
  };

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      {/* Tab bar */}
      {tables.length > 1 && (
        <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
          {tables.map((t, i) => {
            const cnt = countConfigured(t, characteristics);
            const active = i === safeTab;
            return (
              <button
                key={t.table_name}
                onClick={() => handleTabChange(i)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  active
                    ? "border-indigo-500 text-indigo-600 bg-white"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                }`}
              >
                {t.table_name}
                {cnt > 0 && (
                  <span className={`text-xs rounded-full px-1.5 py-0.5 font-semibold ${
                    active ? "bg-indigo-100 text-indigo-600" : "bg-gray-200 text-gray-500"
                  }`}>
                    {cnt}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Active table panel */}
      <div className="p-4">
        {tables.length === 1 && (
          <h3 className="font-medium text-gray-800 mb-2">{tables[0].table_name}</h3>
        )}
        <TablePanel
          key={safeTab}
          table={tables[safeTab]}
          tableIndex={safeTab}
          characteristics={characteristics}
          configuring={configuring}
          setConfiguring={setConfiguring}
          onUpdate={onUpdate}
          onSchemaUpdate={onSchemaUpdate}
        />
      </div>
    </div>
  );
}
