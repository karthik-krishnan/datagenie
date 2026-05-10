export default function ContextInput({ value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">Context</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        placeholder="Describe your data context, relationships, business rules..."
        className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-indigo-500 resize-y"
      />
    </div>
  );
}
