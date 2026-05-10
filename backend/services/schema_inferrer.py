import re
from typing import List, Dict, Any
from datetime import datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+\d][\d\s\-\(\)]{6,}$")
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"]


def _is_int(v: str) -> bool:
    try:
        int(v)
        return True
    except Exception:
        return False


def _is_float(v: str) -> bool:
    try:
        float(v)
        return "." in str(v) or "e" in str(v).lower()
    except Exception:
        return False


def _is_bool(v: str) -> bool:
    return str(v).strip().lower() in ("true", "false", "yes", "no", "0", "1")


def _is_date(v: str) -> bool:
    s = str(v).strip()
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except Exception:
            continue
    return False


def _infer_type(values: List[Any]) -> str:
    cleaned = [str(v).strip() for v in values if v not in (None, "", "null", "NaN")]
    if not cleaned:
        return "string"

    sample = cleaned[:50]

    if all(_is_bool(v) for v in sample) and len(set(v.lower() for v in sample)) <= 2:
        return "boolean"

    if all(EMAIL_RE.match(v) for v in sample):
        return "email"

    if all(PHONE_RE.match(v) for v in sample) and any(c.isdigit() for c in sample[0]):
        digits = sum(c.isdigit() for c in sample[0])
        if digits >= 7:
            return "phone"

    if all(_is_int(v) for v in sample):
        return "integer"

    if all(_is_int(v) or _is_float(v) for v in sample):
        return "float"

    if all(_is_date(v) for v in sample):
        return "date"

    unique = list(set(cleaned))
    if len(unique) <= 20 and len(cleaned) > len(unique):
        return "enum"

    return "string"


def _detect_pattern(name: str, values: List[Any]) -> str:
    n = name.lower()
    if "id" == n or n.endswith("_id"):
        return "identifier"
    if "name" in n:
        return "name"
    if "address" in n:
        return "address"
    if "city" in n:
        return "city"
    if "country" in n:
        return "country"
    if "zip" in n or "postal" in n:
        return "postal_code"
    if "url" in n or "website" in n:
        return "url"
    if "amount" in n or "price" in n or "cost" in n or "total" in n:
        return "currency"
    return "generic"


def _infer_schema_from_context(context_text: str) -> Dict[str, Any]:
    """
    Derive a best-effort schema purely from free-form context text.
    Looks for patterns like:
      - "columns: id, name, email, status"
      - "fields: ..."
      - "table called X with fields ..."
      - comma/newline separated field names
    Returns a single table with inferred columns.
    """
    import re as _re

    text = context_text.strip()

    # Try to find an explicit table name
    table_match = _re.search(r"(?:table|entity|sheet|dataset)\s+(?:called|named|:)?\s*['\"]?(\w+)['\"]?", text, _re.I)
    table_name = table_match.group(1) if table_match else "dataset"

    # Try to extract field names from "columns: ..." or "fields: ..." patterns
    field_match = _re.search(r"(?:columns?|fields?|attributes?)\s*[:\-]?\s*(.+?)(?:\.|$)", text, _re.I | _re.DOTALL)
    if field_match:
        raw = field_match.group(1)
        # split on commas, newlines, semicolons
        names = [n.strip().strip("'\"").replace(" ", "_") for n in _re.split(r"[,\n;|]", raw) if n.strip()]
        names = [n for n in names if n and len(n) <= 50]
    else:
        # Fallback: extract all quoted words or CamelCase/snake_case identifiers that look like field names
        names = _re.findall(r"['\"]([a-zA-Z_][a-zA-Z0-9_]{1,40})['\"]|(?<!\w)([a-z][a-z0-9_]{1,30}_(?:id|name|date|at|status|type|code|no|num|amount|total|count))", text)
        names = [a or b for a, b in names if (a or b)]

    if not names:
        # Last resort: guess a minimal generic schema
        names = ["id", "name", "description", "status", "created_at"]

    # Infer type per column from name heuristics
    TYPE_HINTS = {
        "id": "integer", "uuid": "string", "email": "email", "phone": "phone",
        "date": "date", "_at": "date", "_on": "date", "dob": "date",
        "amount": "float", "price": "float", "total": "float", "cost": "float",
        "count": "integer", "num": "integer", "no": "integer", "qty": "integer",
        "flag": "boolean", "is_": "boolean", "has_": "boolean",
        "status": "enum", "type": "enum", "category": "enum", "gender": "enum",
        "country": "string", "city": "string", "zip": "string", "code": "string",
    }

    def _guess_type(name: str) -> str:
        nl = name.lower()
        for hint, t in TYPE_HINTS.items():
            if hint in nl:
                return t
        return "string"

    cols = [
        {
            "name": n,
            "type": _guess_type(n),
            "sample_values": [],
            "pattern": _detect_pattern(n, []),
            "enum_values": [],
        }
        for n in names
    ]

    return {
        "tables": [{"table_name": table_name, "filename": None, "columns": cols, "row_count": 0}],
        "relationships": [],
    }


def infer_schema(parsed_files: List[Dict[str, Any]], context_text: str = "") -> Dict[str, Any]:
    # Context-only mode: no files uploaded
    if not parsed_files and context_text.strip():
        return _infer_schema_from_context(context_text)

    tables = []
    for pf in parsed_files:
        cols = []
        for c in pf["columns"]:
            values = c["raw_values"]
            ctype = _infer_type(values)
            sample = [str(v) for v in values[:3] if v not in (None, "")]
            unique_vals = []
            if ctype == "enum":
                seen = set()
                for v in values:
                    sv = str(v)
                    if sv and sv not in seen:
                        seen.add(sv)
                        unique_vals.append(sv)
                    if len(unique_vals) >= 20:
                        break
            cols.append({
                "name": c["name"],
                "type": ctype,
                "sample_values": sample,
                "pattern": _detect_pattern(c["name"], values),
                "enum_values": unique_vals if ctype == "enum" else [],
            })
        tables.append({
            "table_name": pf["table_name"],
            "filename": pf["filename"],
            "columns": cols,
            "row_count": len(pf["rows"]),
        })

    relationships = []
    for i, t1 in enumerate(tables):
        for j, t2 in enumerate(tables):
            if i == j:
                continue
            for c1 in t1["columns"]:
                n1 = c1["name"].lower()
                if not (n1.endswith("_id") or n1.endswith("id")):
                    continue
                base = n1.replace("_id", "").replace("id", "")
                if not base:
                    continue
                t2name = t2["table_name"].lower()
                if base in t2name or t2name in base or t2name.rstrip("s") == base or base.rstrip("s") == t2name.rstrip("s"):
                    for c2 in t2["columns"]:
                        n2 = c2["name"].lower()
                        if n2 == "id" or n2.endswith("_id"):
                            relationships.append({
                                "source_table": t1["table_name"],
                                "source_column": c1["name"],
                                "target_table": t2["table_name"],
                                "target_column": c2["name"],
                                "cardinality": "many_to_one",
                                "confidence": 0.85,
                            })
                            break

    seen = set()
    deduped = []
    for r in relationships:
        key = (r["source_table"], r["source_column"], r["target_table"], r["target_column"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return {"tables": tables, "relationships": deduped}
