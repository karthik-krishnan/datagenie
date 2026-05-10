import { useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { api } from "../../api/client.js";

export default function SaveProfileModal() {
  const {
    showSaveProfileModal,
    setShowSaveProfileModal,
    inferredSchema,
    characteristics,
    complianceRules,
    selectedFrameworks,
    relationships,
    outputConfig,
    setProfileId,
    setProfileName,
    setProfileDescription,
  } = useAppStore();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  if (!showSaveProfileModal) return null;

  const close = () => {
    setName("");
    setDescription("");
    setError(null);
    setShowSaveProfileModal(false);
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const profile = await api.createProfile({
        name: name.trim(),
        description: description.trim() || null,
        schema_config: inferredSchema ? JSON.stringify(inferredSchema) : null,
        characteristics: JSON.stringify(characteristics || {}),
        compliance_rules: JSON.stringify({ ...(complianceRules || {}), __selectedFrameworks: selectedFrameworks || [] }),
        relationships: JSON.stringify(relationships || []),
        output_config: JSON.stringify(outputConfig || {}),
      });
      setProfileId(profile.id);
      setProfileName(profile.name);
      setProfileDescription(profile.description);
      close();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-6">
        <h2 className="text-lg font-semibold mb-4">Save as Profile</h2>

        {error && (
          <div className="mb-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. E-commerce Orders Dataset"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this profile generates..."
              rows={3}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={close}
            disabled={saving}
            className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
