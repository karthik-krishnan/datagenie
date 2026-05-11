import { useEffect, useState } from "react";
import { useAppStore } from "../../store/appStore.js";
import { api } from "../../api/client.js";
import { relativeTime } from "../../utils/relativeTime.js";

// ── Static demo starter cards ──────────────────────────────────────────────
const DEMO_STARTERS = [
  {
    id: "demo-ecommerce",
    title: "E-Commerce Orders",
    description: "Customers → Orders → Order Items. PCI, PII, GDPR compliance demo.",
    emoji: "🛒",
    contextKeyword: "ecommerce orders checkout payment customer",
    frameworks: ["PCI", "PII", "GDPR"],
  },
  {
    id: "demo-healthcare",
    title: "Healthcare Patients",
    description: "Patient records with diagnoses, prescriptions, and insurance IDs.",
    emoji: "🏥",
    contextKeyword: "patient clinical hospital diagnosis HIPAA",
    frameworks: ["HIPAA", "PII", "GDPR"],
  },
  {
    id: "demo-hr",
    title: "HR & Payroll",
    description: "Employee roster with salaries, departments, and tax identifiers.",
    emoji: "👩‍💼",
    contextKeyword: "employee payroll salary HR department SOX",
    frameworks: ["SOX", "PII", "GDPR"],
  },
  {
    id: "demo-students",
    title: "Student Records",
    description: "Enrolment, GPA, and financial aid protected under FERPA.",
    emoji: "🎓",
    contextKeyword: "student gpa academic enrollment FERPA",
    frameworks: ["FERPA", "PII", "GDPR"],
  },
  {
    id: "demo-banking",
    title: "Banking & Accounts",
    description: "Customers → Accounts → Transactions + Loans. PCI, GLBA, SOX compliance.",
    emoji: "🏦",
    contextKeyword: "bank account transaction loan kyc AML GLBA",
    frameworks: ["PCI", "GLBA", "SOX", "PII"],
  },
];

const FW_COLORS = {
  PII:   "bg-red-100 text-red-700",
  PCI:   "bg-orange-100 text-orange-700",
  HIPAA: "bg-purple-100 text-purple-700",
  GDPR:  "bg-blue-100 text-blue-700",
  CCPA:  "bg-cyan-100 text-cyan-700",
  SOX:   "bg-yellow-100 text-yellow-800",
  FERPA: "bg-green-100 text-green-700",
  GLBA:  "bg-emerald-100 text-emerald-700",
};

function FrameworkBadges({ complianceJson }) {
  try {
    const blob = JSON.parse(complianceJson || "{}");
    const fws = [...new Set(
      Object.values(blob).flatMap((v) => v?.frameworks || [])
    )].filter((f) => f !== "__selectedFrameworks" && FW_COLORS[f]);
    if (!fws.length) return null;
    return (
      <div className="flex flex-wrap gap-1 mt-1">
        {fws.slice(0, 4).map((fw) => (
          <span key={fw} className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${FW_COLORS[fw]}`}>
            {fw}
          </span>
        ))}
        {fws.length > 4 && (
          <span className="text-xs text-gray-400">+{fws.length - 4}</span>
        )}
      </div>
    );
  } catch {
    return null;
  }
}

export default function ProfilePicker() {
  const { setShowProfilePicker, loadProfile, applyInferResult } = useAppStore();
  const [profiles, setProfiles] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const [demoLoadingId, setDemoLoadingId] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await api.listProfiles();
      // Sort by last_used_at desc, then created_at desc
      const sorted = (Array.isArray(list) ? list : []).sort((a, b) => {
        const ta = new Date(a.last_used_at || a.created_at || 0).getTime();
        const tb = new Date(b.last_used_at || b.created_at || 0).getTime();
        return tb - ta;
      });
      setProfiles(sorted);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleDemoLoad = async (starter) => {
    setDemoLoadingId(starter.id);
    try {
      // Use the dedicated demo endpoint — never calls an LLM, always fast,
      // works correctly regardless of the user's LLM configuration.
      const result = await api.getDemoSchema(starter.contextKeyword);
      applyInferResult(result, 1);
      setShowProfilePicker(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setDemoLoadingId(null);
    }
  };

  const handleLoad = async (id) => {
    setLoadingId(id);
    try {
      const profile = await api.useProfile(id);
      loadProfile(profile);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingId(null);
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

  const q = search.toLowerCase().trim();
  const filtered = profiles.filter((p) =>
    !q ||
    (p.name || "").toLowerCase().includes(q) ||
    (p.description || "").toLowerCase().includes(q)
  );

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <span>🪄</span> DataGenie
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            AI-assisted intelligent test data generator
          </p>
        </div>
        <button
          onClick={() => setShowProfilePicker(false)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 font-medium text-sm"
        >
          <span>+</span> Start Fresh
        </button>
      </div>

      <div className="flex-1 px-8 py-6 max-w-6xl mx-auto w-full">

        {/* ── Demo starter templates ── */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Start with a template
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {DEMO_STARTERS.map((s) => (
              <button
                key={s.id}
                onClick={() => handleDemoLoad(s)}
                disabled={demoLoadingId === s.id}
                className="relative text-left bg-white border border-gray-200 rounded-xl p-4 hover:border-indigo-400 hover:shadow-sm transition-all disabled:opacity-60 group"
              >
                <div className="text-2xl mb-2">{s.emoji}</div>
                <div className="font-medium text-gray-900 text-sm">{s.title}</div>
                <div className="text-xs text-gray-400 mt-1 leading-snug">{s.description}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {s.frameworks.map((fw) => (
                    <span key={fw} className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${FW_COLORS[fw] || "bg-gray-100 text-gray-600"}`}>
                      {fw}
                    </span>
                  ))}
                </div>
                {demoLoadingId === s.id && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-white/80 text-sm text-indigo-600 font-medium">
                    Loading…
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* ── Saved profiles ── */}
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Saved profiles
        </h2>
        {/* Search + count */}
        <div className="flex items-center justify-between mb-4 gap-4">
          <div className="relative flex-1 max-w-sm">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search profiles by name or description…"
              className="w-full pl-8 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
          </div>
          {!loading && (
            <span className="text-sm text-gray-400 whitespace-nowrap">
              {filtered.length} of {profiles.length} profile{profiles.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Profile table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="text-center text-sm text-gray-500 py-16">Loading…</div>
          ) : profiles.length === 0 ? (
            <div className="text-center py-16 px-6">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-gray-600 font-medium">No saved profiles yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Complete a generation and save it as a profile to reuse it later.
              </p>
              <button
                onClick={() => setShowProfilePicker(false)}
                className="mt-4 px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 text-sm font-medium"
              >
                Start your first generation →
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-sm text-gray-400">
              No profiles match <strong>"{search}"</strong>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                  <th className="text-left px-5 py-3 font-medium">Name</th>
                  <th className="text-left px-5 py-3 font-medium">Frameworks</th>
                  <th className="text-left px-4 py-3 font-medium">Last used</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((p) => (
                  <tr
                    key={p.id}
                    className="hover:bg-indigo-50/40 transition-colors group cursor-pointer"
                    onClick={() => confirmDeleteId !== p.id && handleLoad(p.id)}
                  >
                    {/* Name + description */}
                    <td className="px-5 py-4 max-w-xs">
                      <div className="font-medium text-gray-900 truncate">{p.name}</div>
                      {p.description && (
                        <div className="text-xs text-gray-400 mt-0.5 truncate">
                          {p.description}
                        </div>
                      )}
                    </td>

                    {/* Framework badges */}
                    <td className="px-5 py-4 min-w-[160px]">
                      <FrameworkBadges complianceJson={p.compliance_rules} />
                    </td>

                    {/* Last used */}
                    <td className="px-4 py-4 text-gray-500 whitespace-nowrap">
                      {p.last_used_at ? relativeTime(p.last_used_at) : "—"}
                    </td>

                    {/* Created */}
                    <td className="px-4 py-4 text-gray-400 whitespace-nowrap">
                      {p.created_at
                        ? new Date(p.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                        : "—"}
                    </td>

                    {/* Actions */}
                    <td
                      className="px-4 py-4 text-right whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {confirmDeleteId === p.id ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="text-xs text-red-600">Delete?</span>
                          <button
                            onClick={() => handleDelete(p.id)}
                            className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700"
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-50"
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleLoad(p.id)}
                            disabled={loadingId === p.id}
                            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                          >
                            {loadingId === p.id ? "Loading…" : "Load"}
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(p.id)}
                            className="text-xs px-2 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                          >
                            🗑
                          </button>
                        </span>
                      )}
                    </td>
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
