import { useState } from "react";

export default function PreviewTable({ data }) {
  const entries = data ? Object.entries(data) : [];
  const [activeTab, setActiveTab] = useState(0);

  if (!data || entries.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No preview yet. Click "Regenerate preview".
      </div>
    );
  }

  const [tableName, rows] = entries[activeTab] ?? entries[0];
  const cols = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      {/* Tab bar — only shown when there are multiple tables */}
      {entries.length > 1 && (
        <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
          {entries.map(([name, tableRows], i) => (
            <button
              key={name}
              onClick={() => setActiveTab(i)}
              className={[
                "px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
                "focus:outline-none",
                i === activeTab
                  ? "border-b-2 border-indigo-500 text-indigo-600 bg-white"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100",
              ].join(" ")}
            >
              {name}
              <span className="ml-1.5 text-xs text-gray-400 font-normal">
                ({tableRows.length})
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Single-table header (when no tabs) */}
      {entries.length === 1 && (
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 text-sm font-medium text-gray-700">
          {tableName}
          <span className="ml-1.5 text-xs text-gray-400 font-normal">
            ({rows.length} rows)
          </span>
        </div>
      )}

      {/* Data grid */}
      <div className="overflow-x-auto">
        {cols.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-400 text-center">
            No columns to display.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-600 sticky top-0">
              <tr>
                {cols.map((c) => (
                  <th
                    key={c}
                    className="text-left px-3 py-2 whitespace-nowrap font-medium border-b border-gray-100"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  {cols.map((c) => (
                    <td
                      key={c}
                      className="px-3 py-2 whitespace-nowrap text-gray-700 max-w-[200px] truncate"
                      title={String(r[c] ?? "")}
                    >
                      {String(r[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
