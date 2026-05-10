import { useState } from "react";

const TYPES = ["string", "integer", "float", "date", "email", "phone", "boolean", "enum"];

function EditableCell({ value, onChange, placeholder = "" }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    if (draft.trim() && draft !== value) onChange(draft.trim());
    else setDraft(value); // revert if blank
  };

  if (editing) {
    return (
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
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

export default function SchemaCard({ table, onChange }) {
  const [editingName, setEditingName] = useState(false);
  const [tableName, setTableName] = useState(table.table_name);

  const updateColumn = (idx, patch) => {
    const cols = table.columns.map((c, i) => (i === idx ? { ...c, ...patch } : c));
    onChange({ ...table, columns: cols });
  };

  const deleteColumn = (idx) => {
    const cols = table.columns.filter((_, i) => i !== idx);
    onChange({ ...table, columns: cols });
  };

  const addColumn = () => {
    const newCol = {
      name: `column_${table.columns.length + 1}`,
      type: "string",
      sample_values: [],
      pattern: null,
      pii: { is_pii: false },
    };
    onChange({ ...table, columns: [...table.columns, newCol] });
  };

  const commitName = () => {
    setEditingName(false);
    onChange({ ...table, table_name: tableName });
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
              <th className="text-left px-4 py-2">Sample</th>
              <th className="text-left px-4 py-2">Sensitivity</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.columns.map((c, i) => (
              <tr key={i} className="group/row hover:bg-gray-50">
                <td className="px-4 py-2 min-w-[140px]">
                  <EditableCell
                    value={c.name}
                    onChange={(name) => updateColumn(i, { name })}
                  />
                </td>
                <td className="px-4 py-2">
                  <select
                    value={c.type}
                    onChange={(e) => updateColumn(i, { type: e.target.value })}
                    className="bg-white border border-gray-200 rounded px-1 py-0.5 text-xs"
                  >
                    {TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2 text-gray-500 text-xs max-w-[160px] truncate">
                  {(c.sample_values || []).slice(0, 3).join(", ") || <span className="text-gray-300 italic">—</span>}
                </td>
                <td className="px-4 py-2 text-xs">
                  {c.pii?.is_pii || c.pii?.is_sensitive ? (
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                      {c.pii.category || c.pii.field_type || "sensitive"}
                    </span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => deleteColumn(i)}
                    className="opacity-0 group-hover/row:opacity-100 text-gray-300 hover:text-red-400 transition-all text-base leading-none"
                    title="Remove column"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
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
