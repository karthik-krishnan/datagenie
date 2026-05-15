/**
 * VolumeInput — main record count + per-child count configuration.
 *
 * Each child table supports:
 *   - Min / Max count per parent
 *   - Shape: Fixed | Uniform | Realistic
 *
 * Props
 *   value              – root-entity record count (number)
 *   onChange           – called with new root count
 *   fromContext        – true when count came from the context extractor
 *   relationships      – array of relationship objects from inferredSchema
 *   schema             – inferredSchema (to find root tables & labels)
 *   perParentCounts    – { [childTable]: number | { min, max, shape } }
 *   onChildCountChange – (childTable, spec) => void  (spec = { min, max, shape })
 */

const SHAPES = ["Fixed", "Uniform", "Realistic"];

/** Normalise a perParentCounts entry to { min, max, shape } */
function toSpec(val) {
  if (!val && val !== 0) return { min: "", max: "", shape: "Realistic" };
  if (typeof val === "number") return { min: val, max: val, shape: "Fixed" };
  return {
    min: val.min ?? "",
    max: val.max ?? "",
    shape: val.shape ?? "Realistic",
  };
}

const SHAPE_HELP = {
  Fixed:     "Every parent gets the same number of children (midpoint of min–max).",
  Uniform:   "Each parent gets a random count, evenly spread between min and max.",
  Realistic: "Most parents get fewer children; a handful get many (power-law skew).",
};

export default function VolumeInput({
  value,
  onChange,
  fromContext,
  relationships = [],
  schema = null,
  perParentCounts = {},
  onChildCountChange,
}) {
  // Derive one-to-many relationships (parent → child)
  const manyToOneRels = relationships.filter(
    (r) => r.cardinality === "one_to_many" || !r.cardinality
  );

  // Root tables = appear in schema but never as target_table in a one_to_many rel
  const childTables = new Set(manyToOneRels.map((r) => r.target_table));
  const allTables = schema?.tables?.map((t) => t.table_name) || [];
  const rootTables = allTables.filter((t) => !childTables.has(t));
  const hasMultipleTables = allTables.length > 1;

  const rootLabel =
    hasMultipleTables && rootTables.length === 1
      ? `How many ${rootTables[0]} records?`
      : "How many records?";

  const updateSpec = (child, field, val) => {
    const current = toSpec(perParentCounts[child]);
    onChildCountChange(child, { ...current, [field]: val });
  };

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
          max={10000}
          value={value || ""}
          placeholder="e.g. 100"
          onChange={(e) => {
            const n = parseInt(e.target.value || "0", 10);
            onChange(Math.min(n, 10000));
          }}
          className="w-48 border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
        />
        {value > 9000 && (
          <p className="text-xs text-amber-600 mt-1">
            Large volumes may take a few seconds to generate. Maximum is 10,000 root records.
          </p>
        )}
      </div>

      {/* ── Per-child counts ── */}
      {manyToOneRels.length > 0 && onChildCountChange && (
        <div className="border border-gray-200 rounded-xl p-4 space-y-4">
          <div>
            <h3 className="text-sm font-medium text-gray-800">Child record counts</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Control how many child rows each parent row produces.
            </p>
          </div>

          {manyToOneRels.map((rel) => {
            const child = rel.target_table;
            const parent = rel.source_table;
            const spec = toSpec(perParentCounts[child]);

            return (
              <div key={`${child}-${parent}`} className="space-y-2">
                {/* Label */}
                <div className="text-sm text-gray-700">
                  <span className="font-medium">{child}</span>
                  <span className="text-gray-400 mx-1">per</span>
                  <span className="font-medium">{parent}</span>
                </div>

                {/* Min / Max inputs */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <label className="text-xs text-gray-500 w-7">Min</label>
                    <input
                      type="number"
                      min={0}
                      max={1000}
                      value={spec.min}
                      placeholder="1"
                      onChange={(e) => updateSpec(child, "min", parseInt(e.target.value || "0", 10))}
                      className="w-20 border border-gray-300 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-indigo-500"
                    />
                  </div>
                  <span className="text-gray-400 text-sm">–</span>
                  <div className="flex items-center gap-1.5">
                    <label className="text-xs text-gray-500 w-7">Max</label>
                    <input
                      type="number"
                      min={0}
                      max={1000}
                      value={spec.max}
                      placeholder="5"
                      onChange={(e) => updateSpec(child, "max", parseInt(e.target.value || "0", 10))}
                      className="w-20 border border-gray-300 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                {/* Shape chips */}
                <div className="flex items-center gap-2 flex-wrap">
                  {SHAPES.map((s) => (
                    <button
                      key={s}
                      onClick={() => updateSpec(child, "shape", s)}
                      className={`text-xs px-3 py-1 rounded-full border transition-all ${
                        spec.shape === s
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "bg-white text-gray-600 border-gray-300 hover:border-indigo-400 hover:text-indigo-600"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                  <span className="text-xs text-gray-400 ml-1">{SHAPE_HELP[spec.shape]}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
