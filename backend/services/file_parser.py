import csv
import json
import io
from typing import Dict, Any, List
import pandas as pd
import yaml
import xmltodict


def _columns_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    seen = []
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.append(k)
    cols = []
    for name in seen:
        values = [r.get(name) for r in rows]
        cols.append({"name": name, "raw_values": values})
    return cols


def parse_file(file_path: str, extension: str) -> Dict[str, Any]:
    ext = (extension or "").lower().lstrip(".")

    if ext == "csv":
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        rows = df.to_dict(orient="records")
    elif ext == "tsv":
        df = pd.read_csv(file_path, sep="\t", dtype=str, keep_default_na=False)
        rows = df.to_dict(orient="records")
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(file_path, dtype=str)
        df = df.fillna("")
        rows = df.to_dict(orient="records")
    elif ext == "json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            list_keys = [k for k, v in data.items() if isinstance(v, list)]
            if list_keys:
                rows = data[list_keys[0]]
            else:
                rows = [data]
        else:
            rows = []
    elif ext in ("yaml", "yml"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            list_keys = [k for k, v in data.items() if isinstance(v, list)]
            if list_keys:
                rows = data[list_keys[0]]
            else:
                rows = [data]
        else:
            rows = []
    elif ext == "xml":
        with open(file_path, "r", encoding="utf-8") as f:
            doc = xmltodict.parse(f.read())
        rows = []
        if isinstance(doc, dict):
            root_key = list(doc.keys())[0]
            inner = doc[root_key]
            if isinstance(inner, dict):
                list_keys = [k for k, v in inner.items() if isinstance(v, list)]
                if list_keys:
                    rows = inner[list_keys[0]]
                else:
                    inner_lists = [v for v in inner.values() if isinstance(v, list)]
                    rows = inner_lists[0] if inner_lists else [inner]
            elif isinstance(inner, list):
                rows = inner
        rows = [dict(r) if isinstance(r, dict) else {"value": r} for r in rows]
    else:
        raise ValueError(f"Unsupported extension: {ext}")

    rows = [{str(k): v for k, v in r.items()} for r in rows if isinstance(r, dict)]
    columns = _columns_from_rows(rows)

    return {"rows": rows, "columns": columns}
