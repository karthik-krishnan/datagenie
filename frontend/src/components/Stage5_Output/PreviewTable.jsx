export default function PreviewTable({ data }) {
  if (!data) return <div className="text-sm text-gray-500">No preview yet. Click "Regenerate preview".</div>;

  return (
    <div className="space-y-4">
      {Object.entries(data).map(([tableName, rows]) => {
        const cols = rows.length > 0 ? Object.keys(rows[0]) : [];
        return (
          <div key={tableName} className="border border-gray-200 rounded-xl overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 text-sm font-medium">{tableName}</div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    {cols.map((c) => (
                      <th key={c} className="text-left px-3 py-2 whitespace-nowrap">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((r, i) => (
                    <tr key={i}>
                      {cols.map((c) => (
                        <td key={c} className="px-3 py-2 whitespace-nowrap">{String(r[c] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
