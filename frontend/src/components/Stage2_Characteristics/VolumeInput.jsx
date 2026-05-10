/**
 * VolumeInput — main record count + optional per-child counts for relational data.
 *
 * When the inferred schema has multiple tables connected by many-to-one
 * relationships we show extra inputs so the user can specify how many child
 * records to generate per parent row (e.g. "3 orders per customer").
 *
 * Props
 *   value            – root-entity record count (number)
 *   onChange          – called with new root count
 *   fromContext       – true when count came from the context extractor
 *   relationships     – array of relationship objects from inferredSchema
 *   schema            – inferredSchema (to find root tables & labels)
 *   perParentCounts   – { [childTable]: number }
 *   onChildCountChange – (childTable, count) => void
 */
export default function VolumeInput({
  value,
  onChange,
  fromContext,
  relationships = [],
  schema = null,
  perParentCounts = {},
  onChildCountChange,
}) {
  // Derive many-to-one relationships (child → parent)
  const manyToOneRels = relationships.filter(
    (r) => r.cardinality === "many_to_one" || !r.cardinality
  );

  // Root tables = appear in schema but never as source_table in a many_to_one rel
  const childTables = new Set(manyToOneRels.map((r) => r.source_table));
  const allTables = schema?.tables?.map((t) => t.table_name) || [];
  const rootTables = allTables.filter((t) => !childTables.has(t));
  const hasMultipleTables = allTables.length > 1;

  // Label the main input with the root table name when unambiguous
  const rootLabel =
    hasMultipleTables && rootTables.length === 1
      ? `How many ${rootTables[0]} records?`
      : "How many records?";

  return (
    <div className="space-y-4">
      {/* ── Root / total volume ── */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {rootLabel}
          {fromContext && (
            <span className="ml-2 text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full font-normal">
              from your description
            </span>
          )}
        </label>
        <input
          type="number"
          min={1}
          max={1000000}
          value={value || ""}
          placeholder="e.g. 100"
          onChange={(e) => onChange(parseInt(e.target.value || "0", 10))}
          className="w-48 border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
        />
      </div>

      {/* ── Per-child counts (only shown when there are many-to-one rels) ── */}
      {manyToOneRels.length > 0 && onChildCountChange && (
        <div className="border border-gray-200 rounded-xl p-4 space-y-3">
          <div>
            <h3 className="text-sm font-medium text-gray-800">Child record counts</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Set how many related records to generate per parent row.
            </p>
          </div>

          {manyToOneRels.map((rel) => {
            const child = rel.source_table;
            const parent = rel.target_table;
            const currentVal = perParentCounts[child] ?? "";
            return (
              <div key={`${child}-${parent}`} className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={currentVal}
                  placeholder="3"
                  onChange={(e) =>
                    onChildCountChange(child, parseInt(e.target.value || "0", 10))
                  }
                  className="w-20 border border-gray-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
                <span className="text-sm text-gray-700">
                  <span className="font-medium">{child}</span>
                  <span className="text-gray-400 mx-1">per</span>
                  <span className="font-medium">{parent}</span>
                </span>
              </div>
            );
          })}

          <p className="text-xs text-gray-400 pt-1">
            Default is 3 per parent if left blank.
          </p>
        </div>
      )}
    </div>
  );
}
