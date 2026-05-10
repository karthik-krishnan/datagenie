import ChipSelector from "../common/ChipSelector.jsx";

const FORMAT_LABELS = {
  csv: "CSV",
  tsv: "TSV",
  json: "JSON",
  jsonlines: "JSON Lines",
  xlsx: "Excel",
  xml: "XML",
  yaml: "YAML",
  parquet: "Parquet",
};
const LABEL_TO_ID = Object.fromEntries(Object.entries(FORMAT_LABELS).map(([k, v]) => [v, k]));

export default function FormatPicker({ outputConfig, onChange, multiEntity }) {
  const labels = (outputConfig.formats || []).map((id) => FORMAT_LABELS[id] || id);

  const onLabelChange = (next) => {
    const ids = next.map((l) => LABEL_TO_ID[l] || l);
    onChange({ formats: ids });
  };

  const hasJson = outputConfig.formats?.includes("json");
  const hasXml = outputConfig.formats?.includes("xml");

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Output formats</label>
        <ChipSelector
          options={Object.values(FORMAT_LABELS)}
          value={labels}
          onChange={onLabelChange}
          allowCustom
          multi
          customPlaceholder="Custom format..."
        />
      </div>

      {hasJson && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">JSON style</label>
          <ChipSelector
            options={["Array of objects", "Nested", "JSON Lines"]}
            value={
              outputConfig.json_options?.json_mode === "jsonlines"
                ? "JSON Lines"
                : outputConfig.json_options?.json_mode === "nested"
                ? "Nested"
                : "Array of objects"
            }
            onChange={(v) => {
              const mode = v === "JSON Lines" ? "jsonlines" : v === "Nested" ? "nested" : "array";
              onChange({ json_options: { json_mode: mode } });
            }}
          />
        </div>
      )}

      {hasXml && (
        <div className="flex gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">XML root element</label>
            <input
              value={outputConfig.xml_options?.xml_root || "root"}
              onChange={(e) => onChange({ xml_options: { ...outputConfig.xml_options, xml_root: e.target.value } })}
              className="border border-gray-300 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Row element name</label>
            <input
              value={outputConfig.xml_options?.xml_row || "row"}
              onChange={(e) => onChange({ xml_options: { ...outputConfig.xml_options, xml_row: e.target.value } })}
              className="border border-gray-300 rounded-lg px-3 py-2"
            />
          </div>
        </div>
      )}

      {multiEntity && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Packaging</label>
          <ChipSelector
            options={["One ZIP (separate files)", "Single merged file"]}
            value={outputConfig.packaging === "merged" ? "Single merged file" : "One ZIP (separate files)"}
            onChange={(v) => onChange({ packaging: v === "Single merged file" ? "merged" : "one_file_per_entity" })}
          />
          <p className="text-xs text-gray-400 mt-1">
            {outputConfig.packaging === "merged"
              ? "All tables combined into one file with an _entity column."
              : "Each table as its own file, bundled in a ZIP."}
          </p>
        </div>
      )}
    </div>
  );
}
