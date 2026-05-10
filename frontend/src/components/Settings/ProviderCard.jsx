export default function ProviderCard({ id, title, subtitle, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={
        "text-left p-4 rounded-xl border-2 transition bg-white " +
        (selected ? "border-indigo-600 ring-2 ring-indigo-100" : "border-gray-200 hover:border-gray-300")
      }
    >
      <div className="font-semibold text-gray-900">{title}</div>
      <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
    </button>
  );
}
