import { useState } from "react";

const CARDS = ["one_to_one", "one_to_many", "many_to_one", "many_to_many"];
const CARD_LABELS = { one_to_one: "1 : 1", one_to_many: "1 : N", many_to_one: "N : 1", many_to_many: "N : N" };

// ── Validation ────────────────────────────────────────────────────────────────
function validate(r, relationships, currentIndex = -1) {
  if (!r.source_table)  return "Select a source table.";
  if (!r.target_table)  return "Select a target table.";
  if (r.source_table === r.target_table) return "Source and target must be different tables.";
  if (!r.source_column) return "Select a source column.";
  if (!r.target_column) return "Select a target column.";

  const others = relationships.filter((_, i) => i !== currentIndex);
  const dup = others.some(
    (rel) =>
      (rel.source_table === r.source_table && rel.target_table === r.target_table) ||
      (rel.source_table === r.target_table && rel.target_table === r.source_table),
  );
  if (dup) return "A relationship between these two tables already exists.";
  return null;
}

// Tables already paired with sourceTbl (excluding currentIndex row)
function occupiedTargets(sourceTbl, relationships, currentIndex = -1) {
  return new Set(
    relationships
      .filter((_, i) => i !== currentIndex)
      .flatMap((rel) => {
        if (rel.source_table === sourceTbl) return [rel.target_table];
        if (rel.target_table === sourceTbl) return [rel.source_table];
        return [];
      }),
  );
}

// ── Reusable labeled select ───────────────────────────────────────────────────
function FieldSelect({ label, value, onChange, options, placeholder, disabled }) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</label>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => {
          const newVal = e.target.value;
          // Guard against spurious onChange("") events that browsers fire when
          // the option list is updated by React while a value is already selected.
          if (!newVal && value) return;
          onChange(newVal);
        }}
        className={
          "border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-indigo-500 w-full " +
          (disabled ? "border-gray-200 text-gray-400 cursor-not-allowed" : "border-gray-300")
        }
      >
        {/* Only render the placeholder option when no value is selected — this
            prevents the browser from "snapping" to the empty option when the
            options list changes during a React re-render. */}
        {(!value && placeholder) && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

// ── Cardinality chip row ──────────────────────────────────────────────────────
function CardinalityPicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400">Cardinality</span>
      <div className="flex gap-1">
        {CARDS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onChange(c)}
            className={
              "px-2.5 py-0.5 rounded-full text-xs border transition " +
              (value === c
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-600 border-gray-300 hover:border-indigo-400")
            }
          >
            {CARD_LABELS[c]}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function RelationshipMapper({ schema, relationships, onUpdate }) {
  const [adding, setAdding]       = useState(false);
  const [draft, setDraft]         = useState({ source_table: "", source_column: "", target_table: "", target_column: "", cardinality: "many_to_one" });
  const [draftError, setDraftError] = useState(null);
  const [rowErrors, setRowErrors] = useState({});   // index → error string | null

  const tables  = schema?.tables || [];
  const allTbls = tables.map((t) => t.table_name);
  const colsFor = (tn) => (tables.find((t) => t.table_name === tn)?.columns || []).map((c) => c.name);

  // Available target tables for a given source (excludes same table + already-paired tables)
  const availableTargets = (sourceTbl, currentIndex = -1) => {
    if (!sourceTbl) return [];
    const occupied = occupiedTargets(sourceTbl, relationships, currentIndex);
    return allTbls.filter((t) => t !== sourceTbl && !occupied.has(t));
  };

  // ── Edit existing row ───────────────────────────────────────────────────────
  const update = (i, patch) => {
    const current = relationships[i];
    let updated = { ...current, ...patch };
    // Only clear downstream when the value actually changed — re-selecting the
    // same table must NOT wipe existing column/target selections.
    if ("source_table" in patch && patch.source_table !== current.source_table) {
      updated.source_column = "";
      updated.target_table  = "";
      updated.target_column = "";
    }
    if ("target_table" in patch && patch.target_table !== current.target_table) {
      updated.target_column = "";
    }
    const err = validate(updated, relationships, i);
    setRowErrors((prev) => ({ ...prev, [i]: err }));
    onUpdate(relationships.map((r, idx) => (idx === i ? updated : r)));
  };

  const remove = (i) => {
    onUpdate(relationships.filter((_, idx) => idx !== i));
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[i];
      return next;
    });
  };

  // ── Add new row ─────────────────────────────────────────────────────────────
  const add = () => {
    const err = validate(draft, relationships);
    if (err) { setDraftError(err); return; }
    onUpdate([...relationships, { ...draft, confidence: 1.0 }]);
    setDraft({ source_table: "", source_column: "", target_table: "", target_column: "", cardinality: "many_to_one" });
    setDraftError(null);
    setAdding(false);
  };

  const updateDraft = (patch) => {
    let next = { ...draft, ...patch };
    if ("source_table" in patch && patch.source_table !== draft.source_table) {
      next.source_column = ""; next.target_table = ""; next.target_column = "";
    }
    if ("target_table" in patch && patch.target_table !== draft.target_table) {
      next.target_column = "";
    }
    setDraft(next);
    setDraftError(null);
  };

  // ── Render helper — one relationship card ───────────────────────────────────
  const renderRow = ({ r, i, isNew }) => {
    const srcCols     = colsFor(r.source_table);
    const tgtOptions  = isNew ? availableTargets(r.source_table) : availableTargets(r.source_table, i);
    const tgtCols     = colsFor(r.target_table);
    const error       = isNew ? draftError : rowErrors[i];

    return (
      <div className={`rounded-xl p-4 space-y-3 ${isNew ? "border border-dashed border-indigo-300 bg-indigo-50/30" : "border border-gray-200 bg-white"}`}>
        {/* Source → Target grid */}
        <div className="grid grid-cols-[1fr_32px_1fr] gap-2 items-end">
          {/* Source side */}
          <div className="grid grid-cols-2 gap-2">
            <FieldSelect
              label="Source table"
              value={r.source_table}
              onChange={(v) => isNew ? updateDraft({ source_table: v }) : update(i, { source_table: v })}
              options={allTbls}
              placeholder="— table —"
            />
            <FieldSelect
              label="Column"
              value={r.source_column}
              onChange={(v) => isNew ? updateDraft({ source_column: v }) : update(i, { source_column: v })}
              options={srcCols}
              placeholder="— column —"
              disabled={!r.source_table}
            />
          </div>

          {/* Arrow */}
          <div className="flex justify-center pb-2.5 text-gray-400 font-bold">→</div>

          {/* Target side */}
          <div className="grid grid-cols-2 gap-2">
            <FieldSelect
              label="Target table"
              value={r.target_table}
              onChange={(v) => isNew ? updateDraft({ target_table: v }) : update(i, { target_table: v })}
              options={tgtOptions}
              placeholder={r.source_table ? "— table —" : "pick source first"}
              disabled={!r.source_table || tgtOptions.length === 0}
            />
            <FieldSelect
              label="Column"
              value={r.target_column}
              onChange={(v) => isNew ? updateDraft({ target_column: v }) : update(i, { target_column: v })}
              options={tgtCols}
              placeholder="— column —"
              disabled={!r.target_table}
            />
          </div>
        </div>

        {/* Cardinality + actions */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardinalityPicker
            value={r.cardinality}
            onChange={(v) => isNew ? updateDraft({ cardinality: v }) : update(i, { cardinality: v })}
          />
          <div className="flex items-center gap-3">
            {!isNew && r.confidence !== undefined && (
              <span className="text-xs text-gray-400">conf {Math.round(r.confidence * 100)}%</span>
            )}
            {isNew ? (
              <div className="flex gap-2">
                <button onClick={() => { setAdding(false); setDraftError(null); }} className="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
                <button onClick={add} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700">Add</button>
              </div>
            ) : (
              <button onClick={() => remove(i)} className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 border border-transparent hover:border-red-200">
                Remove
              </button>
            )}
          </div>
        </div>

        {/* Inline error */}
        {error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">⚠ {error}</p>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-3">
      {relationships.length === 0 && !adding && (
        <p className="text-sm text-gray-400 py-1">No relationships detected. Add one below.</p>
      )}

      {relationships.map((r, i) =>
        renderRow({ r, i, isNew: false }),
      )}

      {adding
        ? renderRow({ r: draft, i: -1, isNew: true })
        : (
          <button
            onClick={() => setAdding(true)}
            className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            + Add relationship
          </button>
        )}
    </div>
  );
}
