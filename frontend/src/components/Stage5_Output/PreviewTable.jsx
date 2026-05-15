import { useState } from "react";
import { sortColumnsForDisplay } from "../../store/appStore.js";

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
  // Sort: PK first, FK (_id) second, everything else last
  const cols = sortColumnsForDisplay(
    rows.length > 0 ? Object.keys(rows[0]) : [],
    tableName
  );

  return (
    <div>
      {/* Dog-ear tabs — only shown when there are multiple tables */}
      {entries.length > 1 && (
        <div className="flex items-end gap-1 pl-3 overflow-x-auto">
          {entries.map(([name, tableRows], i) => (
            <button
              key={name}
              onClick={() => setActiveTab(i)}
              className={[
                "flex items-center gap-1.5 px-4 py-2 text-sm font-medium whitespace-nowrap",
                "border rounded-t-lg transition-all select-none",
                i === activeTab
                  ? "bg-white border-gray-200 [border-bottom-color:white] text-gray-900 relative z-10 -mb-px"
                  : "bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-50 hover:text-gray-700 mt-1",
              ].join(" ")}
            >
              {name}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${i === activeTab ? "bg-indigo-100 text-indigo-700" : "bg-gray-200 text-gray-500"}`}>
                {tableRows.length}
              </span>
            </button>
          ))}
        </div>
      )}

      <div className={`border border-gray-200 bg-white ${entries.length > 1 ? "rounded-b-xl rounded-tr-xl" : "rounded-xl"} overflow-hidden`}>
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
    </div>
  );
}
