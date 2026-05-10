import { useEffect, useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { api } from "../../api/client.js";
import { relativeTime } from "../../utils/relativeTime.js";

export default function ProfilePicker() {
  const { setShowProfilePicker, loadProfile } = useAppStore();
  const [profiles, setProfiles] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await api.listProfiles();
      setProfiles(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleStartFresh = () => {
    setShowProfilePicker(false);
  };

  const handleLoad = async (id) => {
    try {
      const profile = await api.useProfile(id);
      loadProfile(profile);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.deleteProfile(id);
      setConfirmDeleteId(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const filtered = profiles.filter((p) => {
    const q = search.toLowerCase().trim();
    if (!q) return true;
    return (
      (p.name || "").toLowerCase().includes(q) ||
      (p.description || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-md border border-gray-200 p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold flex items-center justify-center gap-2">
            <span>🪄</span> DataGenie
          </h1>
          <p className="text-sm text-gray-500 mt-2">
            Generate realistic test data in minutes
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-gray-200 rounded-xl p-5 flex flex-col">
            <h2 className="font-semibold text-gray-900 mb-2">Start Fresh</h2>
            <p className="text-sm text-gray-500 mb-4 flex-1">
              Begin a new generation by uploading sample files and inferring a
              schema.
            </p>
            <button
              onClick={handleStartFresh}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 font-medium"
            >
              Start Fresh
            </button>
          </div>

          <div className="border border-gray-200 rounded-xl p-5 flex flex-col">
            <h2 className="font-semibold text-gray-900 mb-2">Load a Profile</h2>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search profiles..."
              className="w-full mb-3 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />

            <div className="flex-1 overflow-y-auto max-h-80 -mx-2">
              {loading ? (
                <div className="text-center text-sm text-gray-500 py-6">
                  Loading...
                </div>
              ) : filtered.length === 0 ? (
                <div className="text-center text-sm text-gray-500 py-6 px-2">
                  {profiles.length === 0
                    ? "No saved profiles yet. Complete a generation and save it as a profile."
                    : "No profiles match your search."}
                </div>
              ) : (
                <ul className="divide-y divide-gray-200">
                  {filtered.map((p) => (
                    <li
                      key={p.id}
                      className="px-2 py-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="font-semibold text-sm text-gray-900">
                        {p.name}
                      </div>
                      {p.description && (
                        <div className="text-xs text-gray-500 truncate">
                          {p.description}
                        </div>
                      )}
                      <div className="text-xs text-gray-400 mt-1">
                        Last used:{" "}
                        {p.last_used_at
                          ? relativeTime(p.last_used_at)
                          : "Never used"}
                        {" · Created: "}
                        {p.created_at
                          ? new Date(p.created_at).toLocaleDateString()
                          : "—"}
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        {confirmDeleteId === p.id ? (
                          <>
                            <span className="text-xs text-red-600">
                              Are you sure?
                            </span>
                            <button
                              onClick={() => handleDelete(p.id)}
                              className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700"
                            >
                              Yes, Delete
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-50"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => handleLoad(p.id)}
                              className="text-xs px-2 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700"
                            >
                              Load
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(p.id)}
                              className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
