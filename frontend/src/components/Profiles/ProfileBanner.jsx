import { useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { api } from "../../api/client.js";

export default function ProfileBanner() {
  const {
    profileId,
    profileName,
    profileDescription,
    inferredSchema,
    characteristics,
    complianceRules,
    selectedFrameworks,
    relationships,
    outputConfig,
    setShowSaveProfileModal,
    clearProfile,
  } = useAppStore();

  const [updating, setUpdating] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState(null);

  if (!profileId) return null;

  const handleUpdate = async () => {
    setUpdating(true);
    setError(null);
    try {
      await api.updateProfile(profileId, {
        name: profileName,
        description: profileDescription,
        schema_config: inferredSchema ? JSON.stringify(inferredSchema) : null,
        characteristics: JSON.stringify(characteristics || {}),
        compliance_rules: JSON.stringify({ ...(complianceRules || {}), __selectedFrameworks: selectedFrameworks || [] }),
        relationships: JSON.stringify(relationships || []),
        output_config: JSON.stringify(outputConfig || {}),
      });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (e) {
      setError(e.message);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="font-medium text-indigo-900 flex items-center gap-2">
            <span>📋</span>
            <span>Profile: {profileName}</span>
          </div>
          {profileDescription && (
            <div className="text-xs text-gray-600 mt-0.5 truncate">
              {profileDescription}
            </div>
          )}
          <div className="text-xs text-gray-500 mt-0.5">
            Unsaved changes apply to this session only
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {savedFlash && (
            <span className="text-xs text-green-700 font-medium">
              ✓ Profile updated
            </span>
          )}
          <button
            onClick={handleUpdate}
            disabled={updating}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {updating ? "Saving..." : "Update Profile"}
          </button>
          <button
            onClick={() => setShowSaveProfileModal(true)}
            className="text-xs px-3 py-1.5 rounded-lg border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-100"
          >
            Save as New Profile
          </button>
          <button
            onClick={clearProfile}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
          >
            Clear Profile
          </button>
        </div>
      </div>
      {error && (
        <div className="mt-2 text-xs text-red-700">{error}</div>
      )}
    </div>
  );
}
