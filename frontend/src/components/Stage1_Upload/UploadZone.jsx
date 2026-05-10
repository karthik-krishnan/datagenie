import { useRef, useState } from "react";

const ACCEPTED = ".csv,.tsv,.xlsx,.xls,.json,.xml,.yaml,.yml";

export default function UploadZone({ files, onFiles }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const addFiles = (list) => {
    const incoming = Array.from(list);
    const merged = [...files];
    for (const f of incoming) {
      if (!merged.find((x) => x.name === f.name && x.size === f.size)) merged.push(f);
    }
    onFiles(merged);
  };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition " +
          (drag ? "border-indigo-500 bg-indigo-50" : "border-gray-300 hover:border-indigo-400 hover:bg-gray-50")
        }
      >
        <div className="text-4xl mb-2">📁</div>
        <div className="text-sm font-medium text-gray-700">Drag and drop files here, or click to browse</div>
        <div className="text-xs text-gray-500 mt-1">CSV, TSV, Excel, JSON, XML, YAML — or skip and describe your schema in the context box below</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-gray-50 px-3 py-2 rounded-lg">
              <span>📄 {f.name} <span className="text-gray-400">({Math.round(f.size / 1024)} KB)</span></span>
              <button
                onClick={() => onFiles(files.filter((_, idx) => idx !== i))}
                className="text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
