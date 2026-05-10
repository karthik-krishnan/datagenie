import csv
import io
import json
import zipfile
from typing import Dict, Any, List, Tuple
import pandas as pd
import yaml
import xmltodict


def _to_csv(rows: List[Dict[str, Any]], delimiter: str = ",") -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    cols = list({k for r in rows for k in r.keys()})
    writer = csv.DictWriter(buf, fieldnames=cols, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _to_json(rows: List[Dict[str, Any]], mode: str = "array") -> bytes:
    if mode == "jsonlines":
        return ("\n".join(json.dumps(r, default=str) for r in rows)).encode("utf-8")
    return json.dumps(rows, indent=2, default=str).encode("utf-8")


def _to_xlsx(data: Dict[str, List[Dict[str, Any]]]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for tname, rows in data.items():
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            df.to_excel(writer, sheet_name=tname[:31] or "Sheet1", index=False)
    return buf.getvalue()


def _to_xml(rows: List[Dict[str, Any]], root: str = "root", row_elem: str = "row") -> bytes:
    doc = {root: {row_elem: rows}}
    return xmltodict.unparse(doc, pretty=True).encode("utf-8")


def _to_yaml(rows: List[Dict[str, Any]]) -> bytes:
    return yaml.safe_dump(rows, sort_keys=False).encode("utf-8")


def _to_parquet(rows: List[Dict[str, Any]]) -> bytes:
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def _ext_for(fmt: str) -> str:
    return {
        "csv": "csv", "tsv": "tsv", "json": "json", "jsonlines": "jsonl",
        "xlsx": "xlsx", "xml": "xml", "yaml": "yaml", "parquet": "parquet",
    }.get(fmt, "txt")


def _mime_for(fmt: str) -> str:
    return {
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "json": "application/json",
        "jsonlines": "application/x-ndjson",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xml": "application/xml",
        "yaml": "application/x-yaml",
        "parquet": "application/octet-stream",
    }.get(fmt, "application/octet-stream")


def _serialize_table(rows: List[Dict[str, Any]], fmt: str, options: Dict[str, Any]) -> bytes:
    if fmt == "csv":
        return _to_csv(rows, ",")
    if fmt == "tsv":
        return _to_csv(rows, "\t")
    if fmt == "json":
        mode = options.get("json_mode", "array")
        return _to_json(rows, mode)
    if fmt == "jsonlines":
        return _to_json(rows, "jsonlines")
    if fmt == "xml":
        root = options.get("xml_root", "root")
        row_elem = options.get("xml_row", "row")
        return _to_xml(rows, root, row_elem)
    if fmt == "yaml":
        return _to_yaml(rows)
    if fmt == "parquet":
        return _to_parquet(rows)
    return _to_csv(rows)


def format_output(
    data: Dict[str, List[Dict[str, Any]]],
    fmt: str,
    options: Dict[str, Any],
    packaging: str = "one_file_per_entity",
) -> Tuple[bytes, str, str]:
    fmt = (fmt or "csv").lower()

    if fmt == "xlsx":
        return _to_xlsx(data), _mime_for("xlsx"), "test_data.xlsx"

    if len(data) == 1:
        tname, rows = next(iter(data.items()))
        ext = _ext_for(fmt)
        return _serialize_table(rows, fmt, options), _mime_for(fmt), f"{tname}.{ext}"

    if packaging == "merged":
        merged = []
        for tname, rows in data.items():
            for r in rows:
                merged.append({"_entity": tname, **r})
        ext = _ext_for(fmt)
        return _serialize_table(merged, fmt, options), _mime_for(fmt), f"test_data.{ext}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        ext = _ext_for(fmt)
        for tname, rows in data.items():
            content = _serialize_table(rows, fmt, options)
            zf.writestr(f"{tname}.{ext}", content)
    return buf.getvalue(), "application/zip", "test_data.zip"
