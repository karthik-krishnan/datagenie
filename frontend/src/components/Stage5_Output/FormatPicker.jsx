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
  const selected = outputConfig.formats?.[0] || "csv";
  const selectedLabel = FORMAT_LABELS[selected] || selected;

  const onLabelChange = (next) => {
    const id = LABEL_TO_ID[next] || next;
    onChange({ formats: [id] });
  };

  const hasJson = selected === "json";
  const hasXml = selected === "xml";

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Output format</label>
        <ChipSelector
          options={Object.values(FORMAT_LABELS)}
          value={selectedLabel}
          onChange={onLabelChange}
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
        <p className="text-xs text-gray-400">
          Multiple tables will be bundled as separate files in a ZIP.
        </p>
      )}
    </div>
  );
}
