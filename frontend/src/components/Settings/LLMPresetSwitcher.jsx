import { useState, useRef, useEffect } from "react";
import { useAppStore } from "../../store/appStore.js";

const PROVIDER_LABEL = {
  anthropic:    "Anthropic",
  openai:       "OpenAI",
  azure:        "Azure OpenAI",
  azure_foundry:"Azure AI Foundry",
  google:       "Google",
  ollama:       "Ollama",
  demo:         "Demo",
};

export default function LLMPresetSwitcher({ currentConfig }) {
  const llmPresets    = useAppStore((s) => s.llmPresets);
  const savePreset    = useAppStore((s) => s.savePreset);
  const deletePreset  = useAppStore((s) => s.deletePreset);
  const activatePreset = useAppStore((s) => s.activatePreset);
  const activePresetId = useAppStore((s) => s.activePresetId);

  const [open, setOpen]       = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving]   = useState(false);
  const popoverRef = useRef(null);
  const inputRef   = useRef(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Focus input when saving section opens
  useEffect(() => {
    if (saving && inputRef.current) inputRef.current.focus();
  }, [saving]);

  const handleActivate = (preset) => {
    activatePreset(preset);
    setOpen(false);
  };

  const handleSave = () => {
    if (!saveName.trim()) return;
    savePreset(saveName, currentConfig);
    setSaveName("");
    setSaving(false);
  };

  const isActive = (preset) => preset.id === activePresetId;

  return (
    <div className="relative" ref={popoverRef}>
      {/* Trigger — small switch icon */}
      <button
        onClick={() => setOpen((v) => !v)}
        title="Switch LLM preset"
        className="p-1 rounded hover:bg-gray-200 transition-colors text-gray-400 hover:text-gray-600"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
          <path d="M8 5a1 1 0 100 2h5.586l-1.293 1.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L13.586 5H8zM12 15a1 1 0 100-2H6.414l1.293-1.293a1 1 0 10-1.414-1.414l-3 3a1 1 0 000 1.414l3 3a1 1 0 001.414-1.414L6.414 15H12z" />
        </svg>
      </button>

      {/* Popover */}
      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-64 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-100">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">LLM Presets</span>
          </div>

          {llmPresets.length === 0 && !saving && (
            <div className="px-3 py-3 text-xs text-gray-400">
              No presets saved yet. Save your current config below.
            </div>
          )}

          {llmPresets.length > 0 && (
            <ul className="max-h-52 overflow-y-auto divide-y divide-gray-50">
              {llmPresets.map((preset) => (
                <li
                  key={preset.id}
                  className={`flex items-center gap-2 px-3 py-2.5 hover:bg-gray-50 cursor-pointer group ${isActive(preset) ? "bg-indigo-50" : ""}`}
                  onClick={() => handleActivate(preset)}
                >
                  {/* Active dot */}
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive(preset) ? "bg-indigo-500" : "bg-transparent"}`} />
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium truncate ${isActive(preset) ? "text-indigo-700" : "text-gray-800"}`}>
                      {preset.name}
                    </div>
                    <div className="text-xs text-gray-400 truncate">
                      {PROVIDER_LABEL[preset.provider] ?? preset.provider}
                      {preset.model ? ` · ${preset.model}` : ""}
                    </div>
                  </div>
                  {/* Delete */}
                  <button
                    onClick={(e) => { e.stopPropagation(); deletePreset(preset.id); }}
                    className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-400 transition-opacity p-0.5 rounded"
                    title="Remove preset"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Save current config */}
          <div className="border-t border-gray-100 px-3 py-2">
            {saving ? (
              <div className="flex gap-1.5">
                <input
                  ref={inputRef}
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setSaving(false); }}
                  placeholder="Preset name…"
                  className="flex-1 text-xs border border-gray-300 rounded px-2 py-1 outline-none focus:border-indigo-400"
                />
                <button
                  onClick={handleSave}
                  disabled={!saveName.trim()}
                  className="text-xs bg-indigo-600 text-white px-2 py-1 rounded disabled:opacity-40 hover:bg-indigo-700"
                >
                  Save
                </button>
                <button
                  onClick={() => { setSaving(false); setSaveName(""); }}
                  className="text-xs text-gray-400 hover:text-gray-600 px-1"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => setSaving(true)}
                className="w-full text-left text-xs text-indigo-600 hover:text-indigo-800 py-0.5"
              >
                + Save current config as preset…
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
