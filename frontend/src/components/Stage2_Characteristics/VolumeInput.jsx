export default function VolumeInput({ value, onChange, hasRelationships, fromContext }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        How many records?
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
      {hasRelationships && (
        <p className="text-xs text-gray-500 mt-1">
          Note: referential integrity may constrain ratios across tables.
        </p>
      )}
    </div>
  );
}
