import ChipSelector from "../common/ChipSelector.jsx";

export default function AttributeDistribution({ table, characteristics, onUpdate }) {
  const setDistribution = (colName, dist) => {
    const key = `${table.table_name}.${colName}`;
    onUpdate({
      distributions: { ...characteristics.distributions, [key]: dist },
    });
  };

  const setTemporal = (colName, days) => {
    const key = `${table.table_name}.${colName}`;
    onUpdate({
      temporal: { ...characteristics.temporal, [key]: { days_back: days } },
    });
  };

  return (
    <div className="space-y-4">
      <h3 className="font-medium text-gray-800">{table.table_name}</h3>
      {table.columns.map((col) => {
        if (col.type === "enum" && col.enum_values?.length) {
          const distKey = `${table.table_name}.${col.name}`;
          const current = characteristics.distributions[distKey] || {};
          return (
            <div key={col.name} className="border-l-2 border-indigo-200 pl-3 py-1">
              <div className="text-sm text-gray-700 mb-2">
                Distribution for <span className="font-medium">{col.name}</span>
              </div>
              <div className="space-y-1">
                {col.enum_values.map((v) => (
                  <div key={v} className="flex items-center gap-2 text-sm">
                    <span className="w-32 text-gray-600">{v}</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={current[v] !== undefined ? Math.round(current[v] * 100) : ""}
                      onChange={(e) => {
                        const pct = parseInt(e.target.value || "0", 10);
                        setDistribution(col.name, { ...current, [v]: pct / 100 });
                      }}
                      placeholder="%"
                      className="w-20 border border-gray-300 rounded px-2 py-1 text-sm"
                    />
                    <span className="text-xs text-gray-400">%</span>
                  </div>
                ))}
              </div>
            </div>
          );
        }

        if (col.type === "date") {
          const tempKey = `${table.table_name}.${col.name}`;
          const current = characteristics.temporal[tempKey];
          const days = current?.days_back;
          const label = days === 30 ? "Last 30 days" : days === 90 ? "Last 90 days" : days === 365 ? "Last year" : days ? `${days} days` : null;
          return (
            <div key={col.name} className="border-l-2 border-indigo-200 pl-3 py-1">
              <div className="text-sm text-gray-700 mb-2">
                Temporal range for <span className="font-medium">{col.name}</span>
              </div>
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

        if (col.type === "boolean") {
          const distKey = `${table.table_name}.${col.name}`;
          const current = characteristics.distributions[distKey] || { true_ratio: 0.5 };
          return (
            <div key={col.name} className="border-l-2 border-indigo-200 pl-3 py-1">
              <div className="text-sm text-gray-700 mb-2">
                True ratio for <span className="font-medium">{col.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round((current.true_ratio || 0.5) * 100)}
                  onChange={(e) => setDistribution(col.name, { true_ratio: parseInt(e.target.value, 10) / 100 })}
                  className="w-64"
                />
                <span className="text-sm w-14 text-gray-600">{Math.round((current.true_ratio || 0.5) * 100)}% true</span>
              </div>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}
