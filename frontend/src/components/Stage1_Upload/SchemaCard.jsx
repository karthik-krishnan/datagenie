import { useState } from "react";

const TYPES = ["string", "integer", "float", "date", "email", "phone", "boolean", "enum"];

const DATE_FORMATS = [
  { label: "YYYY-MM-DD", value: "YYYY-MM-DD" },
  { label: "MM/DD/YYYY", value: "MM/DD/YYYY" },
  { label: "DD/MM/YYYY", value: "DD/MM/YYYY" },
  { label: "YYYY-MM-DD HH:mm:ss", value: "YYYY-MM-DD HH:mm:ss" },
  { label: "MM/DD/YYYY HH:mm:ss", value: "MM/DD/YYYY HH:mm:ss" },
];

// Infer a sensible type from a column name alone (no sample data needed).
// Called when the user adds a new column or when inference returns "string"
// but the name strongly implies a more specific type.
function inferTypeFromName(name) {
  const n = name.toLowerCase();
  if (/\bemail\b/.test(n)) return "email";
  if (/\bphone\b|\bmobile\b|\bcell\b|\btel\b/.test(n)) return "phone";
  if (
    /\bdate\b|\b_at\b|\b_on\b|\bcreated\b|\bupdated\b|\bordered\b|\bshipped\b|\bdob\b|\bbirthday\b/.test(n)
  )
    return "date";
  if (/\b(is_|has_|flag\b|active\b|enabled\b|verified\b)/.test(n)) return "boolean";
  if (
    /\bstatus\b|\btype\b|\bcategory\b|\bgender\b|\brole\b|\bpriority\b|\bstate\b/.test(n)
  )
    return "enum";
  if (
    /\bamount\b|\bprice\b|\bcost\b|\btotal\b|\bsalary\b|\bwage\b|\brate\b|\bbalance\b/.test(n)
  )
    return "float";
  if (
    /\b_id\b|\bcount\b|\bnum\b|\bqty\b|\bquantity\b|\bage\b|\brank\b|\bsequence\b/.test(n)
  )
    return "integer";
  return "string";
}

// Suggest sensible default enum values based on column name
function suggestEnumValues(name) {
  const n = name.toLowerCase();
  if (/status/.test(n))
    return ["active", "inactive", "pending"];
  if (/priority/.test(n))
    return ["low", "medium", "high"];
  if (/gender/.test(n))
    return ["male", "female", "non-binary"];
  if (/role/.test(n))
    return ["admin", "user", "guest"];
  if (/type/.test(n))
    return ["type_a", "type_b", "type_c"];
  if (/category/.test(n))
    return ["category_1", "category_2", "category_3"];
  if (/state/.test(n))
    return ["open", "closed", "archived"];
  return [];
}

// ── Enum value tag editor ───────────────────────────────────────────────────
function EnumValuesEditor({ values = [], onChange }) {
  const [draft, setDraft] = useState("");

  const addTag = (raw) => {
    const newTags = raw
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && !values.includes(s));
    if (newTags.length) onChange([...values, ...newTags]);
    setDraft("");
  };

  const removeTag = (v) => onChange(values.filter((x) => x !== v));

  return (
    <div className="flex flex-wrap gap-1 items-center">
      {values.map((v) => (
        <span
          key={v}
          className="inline-flex items-center gap-0.5 bg-indigo-50 text-indigo-700 text-xs px-2 py-0.5 rounded-full"
        >
          {v}
          <button
            onClick={() => removeTag(v)}
            className="ml-0.5 text-indigo-400 hover:text-red-500 leading-none font-bold"
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
            e.preventDefault();
            addTag(draft);
          }
        }}
        onBlur={() => draft.trim() && addTag(draft)}
        placeholder={values.length ? "add more…" : "type values, press Enter"}
        className="border border-dashed border-gray-300 rounded px-1.5 py-0.5 text-xs outline-none focus:border-indigo-400 w-32 min-w-0"
      />
    </div>
  );
}

// ── Editable column name ───────────────────────────────────────────────────
function EditableCell({ value, onChange, placeholder = "" }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    if (draft.trim() && draft !== value) onChange(draft.trim());
    else setDraft(value);
  };

  if (editing) {
    return (
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") { setDraft(value); setEditing(false); }
        }}
        className="border border-indigo-400 rounded px-1.5 py-0.5 text-sm outline-none w-full bg-white"
        autoFocus
      />
    );
  }

  return (
    <button
      onClick={() => { setDraft(value); setEditing(true); }}
      className="group flex items-center gap-1 text-left w-full"
      title="Click to rename"
    >
      <span className="font-mono text-sm">{value || <span className="text-gray-400 italic">{placeholder}</span>}</span>
      <span className="text-gray-300 group-hover:text-indigo-400 text-xs transition-colors">✎</span>
    </button>
  );
}

// ── Main SchemaCard ────────────────────────────────────────────────────────
export default function SchemaCard({ table, onChange }) {
  const [editingName, setEditingName] = useState(false);
  const [tableName, setTableName] = useState(table.table_name);

  const updateColumn = (idx, patch) => {
    const cols = table.columns.map((c, i) => (i === idx ? { ...c, ...patch } : c));
    onChange({ ...table, columns: cols });
  };

  const handleTypeChange = (idx, newType) => {
    const col = table.columns[idx];
    const patch = { type: newType };

    // When switching to enum: pre-populate with name-based suggestions if empty
    if (newType === "enum" && !(col.enum_values?.length)) {
      const suggestions = suggestEnumValues(col.name);
      if (suggestions.length) patch.enum_values = suggestions;
    }

    // When switching to date: default format
    if (newType === "date" && !col.date_format) {
      patch.date_format = "YYYY-MM-DD";
    }

    updateColumn(idx, patch);
  };

  const deleteColumn = (idx) => {
    const cols = table.columns.filter((_, i) => i !== idx);
    onChange({ ...table, columns: cols });
  };

  const addColumn = () => {
    const name = `column_${table.columns.length + 1}`;
    const inferredType = inferTypeFromName(name);
    const newCol = {
      name,
      type: inferredType,
      sample_values: [],
      pattern: null,
      enum_values: inferredType === "enum" ? suggestEnumValues(name) : [],
      date_format: inferredType === "date" ? "YYYY-MM-DD" : undefined,
      pii: { is_pii: false },
    };
    onChange({ ...table, columns: [...table.columns, newCol] });
  };

  const commitName = () => {
    setEditingName(false);
    onChange({ ...table, table_name: tableName });
  };

  // Auto-correct: if a column was added with type "string" but name implies
  // a better type, surface a hint badge (non-destructive, user clicks to apply)
  const suggestBetterType = (col) => {
    if (col.type !== "string") return null;
    const better = inferTypeFromName(col.name);
    if (better === "string") return null;
    return better;
  };

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      {/* Table name header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        {editingName ? (
          <input
            value={tableName}
            onChange={(e) => setTableName(e.target.value)}
            onBlur={commitName}
            onKeyDown={(e) => e.key === "Enter" && commitName()}
            className="text-base font-semibold border-b border-indigo-500 outline-none bg-white px-1"
            autoFocus
          />
        ) : (
          <button
            onClick={() => setEditingName(true)}
            className="group flex items-center gap-1.5 text-base font-semibold text-gray-900 hover:text-indigo-600"
            title="Click to rename table"
          >
            {table.table_name}
            <span className="text-gray-300 group-hover:text-indigo-400 text-sm transition-colors">✎</span>
          </button>
        )}
        <span className="text-xs text-gray-500">{table.columns.length} columns</span>
      </div>

      {/* Columns table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="text-left px-4 py-2">Column name</th>
              <th className="text-left px-4 py-2">Type</th>
              <th className="text-left px-4 py-2">Values / Format</th>
              <th className="text-left px-4 py-2">Sensitivity</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.columns.map((c, i) => {
              const suggestion = suggestBetterType(c);
              return (
                <tr key={i} className="group/row hover:bg-gray-50">
                  {/* Column name */}
                  <td className="px-4 py-2 min-w-[140px]">
                    <EditableCell
                      value={c.name}
                      onChange={(name) => {
                        // Re-infer type when name changes on a fresh column
                        const patch = { name };
                        if (c.type === "string" || c.type === inferTypeFromName(c.name)) {
                          const newType = inferTypeFromName(name);
                          if (newType !== c.type) {
                            patch.type = newType;
                            if (newType === "enum" && !(c.enum_values?.length)) {
                              patch.enum_values = suggestEnumValues(name);
                            }
                            if (newType === "date" && !c.date_format) {
                              patch.date_format = "YYYY-MM-DD";
                            }
                          }
                        }
                        updateColumn(i, patch);
                      }}
                    />
                  </td>

                  {/* Type selector */}
                  <td className="px-4 py-2">
                    <div className="flex flex-col gap-1">
                      <select
                        value={c.type}
                        onChange={(e) => handleTypeChange(i, e.target.value)}
                        className="bg-white border border-gray-200 rounded px-1 py-0.5 text-xs"
                      >
                        {TYPES.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                      {/* Suggestion badge */}
                      {suggestion && (
                        <button
                          onClick={() => handleTypeChange(i, suggestion)}
                          className="text-[10px] text-indigo-500 hover:text-indigo-700 text-left leading-tight"
                          title={`Auto-detected type: ${suggestion}`}
                        >
                          → use <span className="font-semibold">{suggestion}</span>?
                        </button>
                      )}
                    </div>
                  </td>

                  {/* Context-sensitive: enum values or date format */}
                  <td className="px-4 py-2 min-w-[200px]">
                    {c.type === "enum" ? (
                      <EnumValuesEditor
                        values={c.enum_values || []}
                        onChange={(vals) => updateColumn(i, { enum_values: vals })}
                      />
                    ) : c.type === "date" ? (
                      <select
                        value={c.date_format || "YYYY-MM-DD"}
                        onChange={(e) => updateColumn(i, { date_format: e.target.value })}
                        className="bg-white border border-gray-200 rounded px-1 py-0.5 text-xs"
                      >
                        {DATE_FORMATS.map((f) => (
                          <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-gray-400 text-xs truncate max-w-[160px] block">
                        {(c.sample_values || []).slice(0, 3).join(", ") || <span className="italic">—</span>}
                      </span>
                    )}
                  </td>

                  {/* Sensitivity */}
                  <td className="px-4 py-2 text-xs">
                    {c.pii?.is_pii || c.pii?.is_sensitive ? (
                      <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                        {c.pii.category || c.pii.field_type || "sensitive"}
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Delete */}
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => deleteColumn(i)}
                      className="text-gray-300 hover:text-red-500 hover:bg-red-50 transition-all rounded px-1.5 py-0.5 text-sm font-medium"
                      title="Remove column"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add column */}
      <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
        <button
          onClick={addColumn}
          className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
        >
          <span className="text-base leading-none">+</span> Add column
        </button>
      </div>
    </div>
  );
}
