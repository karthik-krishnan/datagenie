import { useState } from "react";

export default function ChipSelector({
  options = [],
  value,
  onChange,
  allowCustom = false,
  customPlaceholder = "Custom value...",
  multi = false,
}) {
  const [showCustom, setShowCustom] = useState(false);
  const [customVal, setCustomVal] = useState("");

  const isSelected = (opt) => {
    if (multi) return Array.isArray(value) && value.includes(opt);
    return value === opt;
  };

  const handleClick = (opt) => {
    if (multi) {
      const arr = Array.isArray(value) ? [...value] : [];
      const idx = arr.indexOf(opt);
      if (idx >= 0) arr.splice(idx, 1);
      else arr.push(opt);
      onChange(arr);
    } else {
      onChange(opt);
    }
  };

  const submitCustom = () => {
    if (!customVal.trim()) return;
    if (multi) {
      const arr = Array.isArray(value) ? [...value] : [];
      arr.push(customVal.trim());
      onChange(arr);
    } else {
      onChange(customVal.trim());
    }
    setCustomVal("");
    setShowCustom(false);
  };

  return (
    <div className="flex flex-wrap gap-2 items-center">
      {options.map((opt) => {
        const sel = isSelected(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => handleClick(opt)}
            className={
              "px-3 py-1.5 rounded-full text-sm border transition " +
              (sel
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:border-indigo-400")
            }
          >
            {opt}
          </button>
        );
      })}
      {multi &&
        Array.isArray(value) &&
        value
          .filter((v) => !options.includes(v))
          .map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => handleClick(v)}
              className="px-3 py-1.5 rounded-full text-sm border bg-indigo-600 text-white border-indigo-600"
            >
              {v} ×
            </button>
          ))}
      {!multi && value && !options.includes(value) && (
        <span className="px-3 py-1.5 rounded-full text-sm bg-indigo-600 text-white">{value}</span>
      )}
      {allowCustom && !showCustom && (
        <button
          type="button"
          onClick={() => setShowCustom(true)}
          className="px-3 py-1.5 rounded-full text-sm border border-dashed border-gray-400 text-gray-600 hover:border-indigo-400 hover:text-indigo-600"
        >
          + Custom...
        </button>
      )}
      {allowCustom && showCustom && (
        <div className="flex items-center gap-1">
          <input
            value={customVal}
            onChange={(e) => setCustomVal(e.target.value)}
            placeholder={customPlaceholder}
            className="px-3 py-1.5 rounded-full text-sm border border-gray-300 outline-none focus:border-indigo-500"
            onKeyDown={(e) => e.key === "Enter" && submitCustom()}
            autoFocus
          />
          <button
            type="button"
            onClick={submitCustom}
            className="px-3 py-1.5 rounded-full text-sm bg-indigo-600 text-white"
          >
            Add
          </button>
          <button
            type="button"
            onClick={() => {
              setShowCustom(false);
              setCustomVal("");
            }}
            className="px-2 py-1.5 text-sm text-gray-500"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
