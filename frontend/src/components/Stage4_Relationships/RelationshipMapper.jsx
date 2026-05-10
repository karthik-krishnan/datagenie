import { useState } from "react";

const CARDS = ["one_to_one", "one_to_many", "many_to_one", "many_to_many"];

function validate(r, relationships, currentIndex = -1) {
  if (!r.source_table || !r.target_table) return "Select both source and target tables.";
  if (r.source_table === r.target_table) return "Source and target table must be different.";
  if (!r.source_column) return "Select a source column.";
  if (!r.target_column) return "Select a target column.";
  const duplicate = relationships.some((rel, i) =>
    i !== currentIndex &&
    rel.source_table === r.source_table &&
    rel.source_column === r.source_column &&
    rel.target_table === r.target_table &&
    rel.target_column === r.target_column
  );
  if (duplicate) return "This relationship already exists.";
  return null;
}

export default function RelationshipMapper({ schema, relationships, onUpdate }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({
    source_table: "",
    source_column: "",
    target_table: "",
    target_column: "",
    cardinality: "many_to_one",
  });
  const [draftError, setDraftError] = useState(null);

  const tables = schema?.tables || [];
  const colsFor = (tn) => tables.find((t) => t.table_name === tn)?.columns || [];

  const remove = (i) => onUpdate(relationships.filter((_, idx) => idx !== i));

  const update = (i, patch) => {
    const updated = { ...relationships[i], ...patch };
    // Clear column when table changes
    onUpdate(relationships.map((r, idx) => (idx === i ? updated : r)));
  };

  const add = () => {
    const err = validate(draft, relationships);
    if (err) { setDraftError(err); return; }
    onUpdate([...relationships, { ...draft, confidence: 1.0 }]);
    setDraft({ source_table: "", source_column: "", target_table: "", target_column: "", cardinality: "many_to_one" });
    setDraftError(null);
    setAdding(false);
  };

  // Filter target table options to exclude the source table
  const targetTables = (sourceTbl) => tables.filter((t) => t.table_name !== sourceTbl);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {relationships.map((r, i) => (
          <div key={i} className="border border-gray-200 rounded-xl p-3 bg-white flex items-center gap-2 text-sm">
            <select value={r.source_table} onChange={(e) => update(i, { source_table: e.target.value, source_column: "" })} className="border border-gray-200 rounded px-2 py-1">
              {tables.map((t) => <option key={t.table_name} value={t.table_name}>{t.table_name}</option>)}
            </select>
            <span>.</span>
            <select value={r.source_column} onChange={(e) => update(i, { source_column: e.target.value })} className="border border-gray-200 rounded px-2 py-1">
              {colsFor(r.source_table).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <span className="mx-2 text-gray-400">→</span>
            <select value={r.target_table} onChange={(e) => update(i, { target_table: e.target.value, target_column: "" })} className="border border-gray-200 rounded px-2 py-1">
              {targetTables(r.source_table).map((t) => <option key={t.table_name} value={t.table_name}>{t.table_name}</option>)}
            </select>
            <span>.</span>
            <select value={r.target_column} onChange={(e) => update(i, { target_column: e.target.value })} className="border border-gray-200 rounded px-2 py-1">
              {colsFor(r.target_table).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <select value={r.cardinality} onChange={(e) => update(i, { cardinality: e.target.value })} className="border border-gray-200 rounded px-2 py-1 ml-auto">
              {CARDS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
            {r.confidence !== undefined && (
              <span className="text-xs text-gray-500 ml-2">conf {Math.round(r.confidence * 100)}%</span>
            )}
            <button onClick={() => remove(i)} className="text-red-500 hover:text-red-700 ml-2">Remove</button>
          </div>
        ))}
        {relationships.length === 0 && <p className="text-sm text-gray-500">No relationships detected yet.</p>}
      </div>

      {adding ? (
        <div className="border border-dashed border-indigo-300 rounded-xl p-3 bg-indigo-50/40 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select value={draft.source_table} onChange={(e) => setDraft({ ...draft, source_table: e.target.value, source_column: "" })} className="border border-gray-200 rounded px-2 py-1 bg-white">
              <option value="">source table</option>
              {tables.map((t) => <option key={t.table_name} value={t.table_name}>{t.table_name}</option>)}
            </select>
            <select value={draft.source_column} onChange={(e) => setDraft({ ...draft, source_column: e.target.value })} className="border border-gray-200 rounded px-2 py-1 bg-white">
              <option value="">source column</option>
              {colsFor(draft.source_table).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <span className="mx-1 text-gray-400">→</span>
            <select value={draft.target_table} onChange={(e) => setDraft({ ...draft, target_table: e.target.value, target_column: "" })} className="border border-gray-200 rounded px-2 py-1 bg-white">
              <option value="">target table</option>
              {targetTables(draft.source_table).map((t) => <option key={t.table_name} value={t.table_name}>{t.table_name}</option>)}
            </select>
            <select value={draft.target_column} onChange={(e) => setDraft({ ...draft, target_column: e.target.value })} className="border border-gray-200 rounded px-2 py-1 bg-white">
              <option value="">target column</option>
              {colsFor(draft.target_table).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <select value={draft.cardinality} onChange={(e) => setDraft({ ...draft, cardinality: e.target.value })} className="border border-gray-200 rounded px-2 py-1 bg-white">
              {CARDS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
            <button onClick={add} className="px-3 py-1 rounded bg-indigo-600 text-white">Add</button>
            <button onClick={() => { setAdding(false); setDraftError(null); }} className="px-3 py-1 rounded text-gray-500">Cancel</button>
          </div>
          {draftError && <p className="text-xs text-red-500">{draftError}</p>}
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="text-sm text-indigo-600 hover:text-indigo-800">+ Add relationship</button>
      )}
    </div>
  );
}
