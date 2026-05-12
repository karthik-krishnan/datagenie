import { useState, useRef, useEffect } from "react";

const TYPES = ["string", "integer", "float", "date", "email", "phone", "boolean", "enum"];

// ── Sensitivity frameworks available for manual selection ─────────────────────
const FRAMEWORKS = ["PII", "PCI", "HIPAA", "GDPR", "CCPA", "SOX", "FERPA", "GLBA"];

const FW_COLORS = {
  PII:   "bg-red-100 text-red-700",
  PCI:   "bg-orange-100 text-orange-700",
  HIPAA: "bg-purple-100 text-purple-700",
  GDPR:  "bg-blue-100 text-blue-700",
  CCPA:  "bg-cyan-100 text-cyan-700",
  SOX:   "bg-yellow-100 text-yellow-800",
  FERPA: "bg-green-100 text-green-700",
  GLBA:  "bg-emerald-100 text-emerald-700",
};

// Client-side sensitivity detection — mirrors the top entries in the backend
// compliance_detector.py FIELD_CATALOG so newly added / renamed columns get
// auto-classified without a round-trip.
function detectPIIFromName(name) {
  const n = name.toLowerCase();
  const catalog = [
    // PII
    [/\bemail\b/,                           { frameworks: ["PII", "GDPR"],        field_type: "email_address",    default_action: "fake_realistic"    }],
    [/\bphone\b|\bmobile\b|\bcell\b/,       { frameworks: ["PII", "GDPR"],        field_type: "phone_number",     default_action: "fake_realistic"    }],
    [/\bssn\b|\bsocial.sec/,               { frameworks: ["PII"],                 field_type: "ssn",              default_action: "mask"              }],
    [/\bfirst.name\b|\blast.name\b|\bfull.name\b|\b^name$/, { frameworks: ["PII", "GDPR"], field_type: "person_name", default_action: "fake_realistic" }],
    [/\bdob\b|\bdate.of.birth\b|\bbirthday\b/, { frameworks: ["PII", "GDPR"],     field_type: "date_of_birth",    default_action: "format_preserving" }],
    [/\baddress\b|\bstreet\b|\bpostcode\b|\bzip.?code\b/, { frameworks: ["PII", "GDPR"], field_type: "postal_address", default_action: "fake_realistic" }],
    [/\bip.?address\b|\bip.?addr\b/,       { frameworks: ["PII", "GDPR"],        field_type: "ip_address",       default_action: "mask"              }],
    [/\bpassport\b/,                        { frameworks: ["PII", "GDPR"],        field_type: "passport_number",  default_action: "mask"              }],
    [/\bgender\b|\bsex\b/,                  { frameworks: ["PII", "GDPR"],        field_type: "gender",           default_action: "fake_realistic"    }],
    // PCI
    [/\bcredit.?card\b|\bcard.?num\b|\bpan\b/, { frameworks: ["PCI"],             field_type: "card_number",      default_action: "format_preserving" }],
    [/\bcvv\b|\bcvc\b|\bcsc\b/,            { frameworks: ["PCI"],                 field_type: "card_cvv",         default_action: "redact"            }],
    [/\bcard.?expir\b|\bexpiry\b/,          { frameworks: ["PCI"],                field_type: "card_expiry",      default_action: "fake_realistic"    }],
    [/\baccount.?num\b|\bacct.?num\b/,     { frameworks: ["PCI", "GLBA"],         field_type: "account_number",   default_action: "format_preserving" }],
    [/\brouting.?num\b/,                   { frameworks: ["PCI", "GLBA"],         field_type: "routing_number",   default_action: "format_preserving" }],
    [/\biban\b/,                            { frameworks: ["PCI", "GDPR", "GLBA"], field_type: "bank_account",    default_action: "format_preserving" }],
    [/\bswift\b/,                           { frameworks: ["PCI", "GLBA"],        field_type: "swift_bic",        default_action: "format_preserving" }],
    // HIPAA
    [/\bdiagnosis\b|\bdiagnose\b/,         { frameworks: ["HIPAA"],               field_type: "medical_diagnosis",default_action: "fake_realistic"    }],
    [/\bmrn\b|\bmedical.?record\b/,        { frameworks: ["HIPAA"],               field_type: "medical_record_no",default_action: "format_preserving" }],
    [/\bpatient.?id\b/,                    { frameworks: ["HIPAA", "PII"],        field_type: "patient_identifier",default_action: "format_preserving"}],
    [/\binsurance.?id\b|\binsurance.?num\b/,{ frameworks: ["HIPAA", "PII"],       field_type: "insurance_number", default_action: "format_preserving" }],
    [/\bprescription\b|\bdrug.?name\b/,    { frameworks: ["HIPAA"],               field_type: "prescription",     default_action: "fake_realistic"    }],
    // SOX / financial
    [/\bsalary\b|\bwage\b|\bcompensation\b/,{ frameworks: ["SOX", "PII"],         field_type: "salary",           default_action: "mask"              }],
    [/\bbonus\b/,                           { frameworks: ["SOX", "PII"],         field_type: "compensation",     default_action: "mask"              }],
    [/\btax.?id\b|\bein\b|\btin\b/,        { frameworks: ["SOX", "PII"],         field_type: "tax_identifier",   default_action: "format_preserving" }],
    // GLBA / banking
    [/\bcredit.?score\b/,                  { frameworks: ["GLBA", "PII"],         field_type: "credit_score",     default_action: "fake_realistic"    }],
    [/\bkyc\b|\brisk.?rating\b/,           { frameworks: ["GLBA", "PII"],         field_type: "kyc_status",       default_action: "fake_realistic"    }],
  ];
  for (const [re, info] of catalog) {
    if (re.test(n)) {
      return { is_sensitive: true, is_pii: true, frameworks: info.frameworks,
               field_type: info.field_type, default_action: info.default_action,
               recommendations: {}, confidence: 0.85 };
    }
  }
  return { is_sensitive: false, is_pii: false, frameworks: [], field_type: null,
           default_action: null, recommendations: {}, confidence: 0.0 };
}

// ── Sensitivity cell — shows badge; click to edit frameworks manually ─────────
function SensitivityCell({ pii = {}, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const frameworks = pii?.frameworks || [];
  const isSensitive = pii?.is_sensitive || pii?.is_pii || frameworks.length > 0;

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const toggleFramework = (fw) => {
    const next = frameworks.includes(fw)
      ? frameworks.filter((f) => f !== fw)
      : [...frameworks, fw];
    const sensitive = next.length > 0;
    onChange({
      ...pii,
      frameworks: next,
      is_sensitive: sensitive,
      is_pii: sensitive,
      field_type: pii.field_type || (sensitive ? "custom" : null),
      default_action: pii.default_action || (sensitive ? "fake_realistic" : null),
    });
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex flex-wrap gap-1 items-center group"
        title="Click to set sensitivity"
      >
        {isSensitive ? (
          frameworks.map((fw) => (
            <span key={fw} className={`px-2 py-0.5 rounded-full text-xs font-medium ${FW_COLORS[fw] || "bg-gray-100 text-gray-700"}`}>
              {fw}
            </span>
          ))
        ) : (
          <span className="text-gray-300 group-hover:text-indigo-400 text-xs transition-colors">
            — <span className="text-[10px]">set</span>
          </span>
        )}
      </button>

      {open && (
        <div className="absolute z-20 top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg p-3 min-w-[180px]">
          <p className="text-[10px] uppercase text-gray-400 font-medium mb-2 tracking-wide">Frameworks</p>
          <div className="flex flex-col gap-1.5">
            {FRAMEWORKS.map((fw) => (
              <label key={fw} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={frameworks.includes(fw)}
                  onChange={() => toggleFramework(fw)}
                  className="accent-indigo-600"
                />
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${FW_COLORS[fw]}`}>{fw}</span>
              </label>
            ))}
          </div>
          {isSensitive && (
            <button
              onClick={() => { onChange({ is_sensitive: false, is_pii: false, frameworks: [], field_type: null, default_action: null, recommendations: {}, confidence: 0.0 }); setOpen(false); }}
              className="mt-2 w-full text-xs text-red-500 hover:text-red-700 text-left"
            >
              ✕ Clear sensitivity
            </button>
          )}
        </div>
      )}
    </div>
  );
}

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
      pii: detectPIIFromName(name),
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
              <th className="text-left px-4 py-2">Sensitivity <span className="normal-case text-gray-400 font-normal">(click to edit)</span></th>
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
                        // Re-detect sensitivity when name changes (only if not
                        // manually overridden — confidence < 1 means auto-detected)
                        if (!c.pii || c.pii.confidence < 1) {
                          patch.pii = detectPIIFromName(name);
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
                  <td className="px-4 py-2">
                    <SensitivityCell
                      pii={c.pii}
                      onChange={(newPii) => updateColumn(i, { pii: { ...newPii, confidence: 1.0 } })}
                    />
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
