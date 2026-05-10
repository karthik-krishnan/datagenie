import { useAppStore } from "../../store/appStore.js";

const STAGES = [
  { n: 1, label: "Upload & Context" },
  { n: 2, label: "Characteristics" },
  { n: 3, label: "Compliance" },
  { n: 4, label: "Relationships" },
  { n: 5, label: "Output & Preview" },
];

export default function StageIndicator() {
  const currentStage = useAppStore((s) => s.currentStage);
  const setStage = useAppStore((s) => s.setStage);
  const inferredSchema = useAppStore((s) => s.inferredSchema);
  const contextText = useAppStore((s) => s.contextText);
  const uploadedFiles = useAppStore((s) => s.uploadedFiles);

  const piiAvailable = !!inferredSchema?.pii_detected;
  const relAvailable = uploadedFiles.length > 1 || /relationship/i.test(contextText || "");

  const isAvailable = (n) => {
    if (n === 3) return piiAvailable;
    if (n === 4) return relAvailable;
    return true;
  };

  return (
    <div className="space-y-2">
      {STAGES.map((s) => {
        const completed = currentStage > s.n;
        const active = currentStage === s.n;
        const skipped = !isAvailable(s.n);
        return (
          <button
            key={s.n}
            onClick={() => isAvailable(s.n) && setStage(s.n)}
            disabled={skipped}
            className={
              "w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-lg transition " +
              (active
                ? "bg-indigo-600 text-white"
                : completed
                ? "bg-green-50 text-green-800 hover:bg-green-100"
                : skipped
                ? "text-gray-400 cursor-not-allowed"
                : "text-gray-700 hover:bg-gray-200")
            }
          >
            <span
              className={
                "h-7 w-7 rounded-full flex items-center justify-center text-sm font-medium " +
                (active
                  ? "bg-white text-indigo-600"
                  : completed
                  ? "bg-green-600 text-white"
                  : skipped
                  ? "bg-gray-200 text-gray-400"
                  : "bg-gray-300 text-gray-700")
              }
            >
              {completed ? "✓" : s.n}
            </span>
            <div className="flex-1">
              <div className="text-sm font-medium">{s.label}</div>
              {skipped && <div className="text-[10px]">not needed</div>}
            </div>
          </button>
        );
      })}
    </div>
  );
}
