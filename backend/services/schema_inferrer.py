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


# ─── Semantic type inference from column name ────────────────────────────────
# Maps regex patterns against the lowercased column name.  Order matters —
# earlier entries win.
_SEMANTIC_TYPE_RULES: List[tuple] = [
    # Contact
    (r"\bemail\b",                             "email"),
    (r"\bphone\b|\bmobile\b|\bcell\b|\btel\b", "phone"),
    # Dates — any name that contains "date", ends in _at/_on, or common names
    (r"\bdate\b|\b_at\b|_at$|_on$|\bscheduled\b|\bordered\b|\bshipped\b"
     r"|\bdelivered\b|\bcreated\b|\bupdated\b|\bdob\b|\bbirthday\b",
     "date"),
    # Booleans
    (r"^is_|^has_|\bflag\b|\bactive\b|\benabled\b|\bverified\b", "boolean"),
    # Enums — high-cardinality-name fields that are almost always categoricals
    (r"\bstatus\b|\btype\b|\bcategory\b|\bgender\b|\brole\b"
     r"|\bpriority\b|\bstate\b|\bstage\b|\bcondition\b",
     "enum"),
    # Numerics
    (r"\bamount\b|\bprice\b|\bcost\b|\btotal\b|\bsalary\b"
     r"|\bwage\b|\brate\b|\bbalance\b|\brevenue\b|\bfee\b",
     "float"),
    (r"\b_id\b|_id$|\bcount\b|\bnum\b|\bqty\b|\bquantity\b"
     r"|\bage\b|\brank\b|\bsequence\b|\bseq\b",
     "integer"),
    # UUIDs stay as string (not integer)
    (r"\buuid\b|\bguid\b",                     "string"),
]

# Sensible default enum values keyed by name fragment
_ENUM_SUGGESTIONS: List[tuple] = [
    (r"\bstatus\b",   ["active", "inactive", "pending"]),
    (r"\bpriority\b", ["low", "medium", "high"]),
    (r"\bgender\b",   ["male", "female", "non-binary"]),
    (r"\brole\b",     ["admin", "user", "guest"]),
    (r"\bstage\b",    ["draft", "in_progress", "complete"]),
    (r"\btype\b",     ["type_a", "type_b", "type_c"]),
    (r"\bcategory\b", ["category_1", "category_2", "category_3"]),
    (r"\bstate\b",    ["open", "closed", "archived"]),
]


def _guess_col_type(name: str) -> str:
    nl = name.lower()
    for pattern, ctype in _SEMANTIC_TYPE_RULES:
        if re.search(pattern, nl):
            return ctype
    return "string"


def _suggest_enum_values(name: str) -> List[str]:
    nl = name.lower()
    for pattern, vals in _ENUM_SUGGESTIONS:
        if re.search(pattern, nl):
            return vals
    return []


def _make_col(name: str) -> Dict[str, Any]:
    ctype = _guess_col_type(name)
    col: Dict[str, Any] = {
        "name": name,
        "type": ctype,
        "sample_values": [],
        "pattern": _detect_pattern(name, []),
        "enum_values": _suggest_enum_values(name) if ctype == "enum" else [],
    }
    if ctype == "date":
        col["date_format"] = "YYYY-MM-DD"
    return col


def _parse_field_list(raw: str) -> List[str]:
    """Split a comma/semicolon-delimited field string into clean column names."""
    names = [
        n.strip().strip("'\"").replace(" ", "_")
        for n in re.split(r"[,;|]", raw)
        if n.strip()
    ]
    # Keep only valid identifier-like names, skip long prose fragments
    return [n for n in names if n and len(n) <= 50 and re.match(r"^[A-Za-z_]\w*$", n)]


def _detect_multi_table_entries(text: str) -> List[tuple]:
    """
    Return a list of (table_name, [field_names]) when text describes multiple
    tables.  Recognises two formats:

    Format A — numbered list with em-dash / colon separator:
        1. customers — id, first_name, last_name, email
        2. orders — id, customer_id, total_amount, status

    Format B — repeated "table/entity/dataset X:" sections:
        Table customers: id, name, email
        Table orders: id, customer_id, total
    """
    entries: List[tuple] = []

    # Format A: lines that start with a number + table name + separator + fields
    # The field list runs to end-of-line (multi-line descriptions OK if separated
    # by a blank line, so we only capture up to the first newline of fields).
    numbered = re.findall(
        r"^\s*\d+\.\s+([A-Za-z_]\w*)\s*[—–:\-]\s*([^\n]+)",
        text,
        re.MULTILINE,
    )
    if len(numbered) >= 2:
        for table_name, fields_raw in numbered:
            fields = _parse_field_list(fields_raw)
            if fields:
                entries.append((table_name.lower(), fields))
        if len(entries) >= 2:
            return entries

    # Format B: "table/entity/dataset <name>:" or "— <name>:" sections
    labeled = re.findall(
        r"(?:^|\n)\s*(?:table|entity|dataset)\s+[\"']?([A-Za-z_]\w*)[\"']?\s*[:\-—–]\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if len(labeled) >= 2:
        entries = []
        for table_name, fields_raw in labeled:
            fields = _parse_field_list(fields_raw)
            if fields:
                entries.append((table_name.lower(), fields))
        if len(entries) >= 2:
            return entries

    return []


def _relationships_from_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Auto-detect FK relationships from column naming conventions, same logic
    as the file-based relationship detection in infer_schema().
    """
    relationships = []
    seen: set = set()

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
                if (
                    base in t2name
                    or t2name in base
                    or t2name.rstrip("s") == base
                    or base.rstrip("s") == t2name.rstrip("s")
                ):
                    for c2 in t2["columns"]:
                        n2 = c2["name"].lower()
                        if n2 == "id" or n2 == f"{t2name}_id":
                            key = (t2["table_name"], c2["name"], t1["table_name"], c1["name"])
                            if key not in seen:
                                seen.add(key)
                                relationships.append({
                                    "source_table":  t2["table_name"],
                                    "source_column": c2["name"],
                                    "target_table":  t1["table_name"],
                                    "target_column": c1["name"],
                                    "cardinality":   "one_to_many",
                                    "confidence":    0.85,
                                })
                            break

    return relationships


def _infer_schema_from_context(context_text: str) -> Dict[str, Any]:
    """
    Derive a best-effort schema from free-form context text.

    Multi-table mode (preferred): when the text uses a numbered list or
    repeated "table X:" sections to describe several entities, each one
    becomes its own table and FK relationships are auto-detected.

    Single-table fallback: original behaviour — extract columns from the
    first "columns: ..." / "fields: ..." pattern found and return one table.
    """
    text = context_text.strip()

    # ── Try multi-table detection first ──────────────────────────────────────
    multi_entries = _detect_multi_table_entries(text)
    if multi_entries:
        tables = [
            {
                "table_name": tname,
                "filename":   None,
                "columns":    [_make_col(n) for n in col_names],
                "row_count":  0,
            }
            for tname, col_names in multi_entries
        ]
        return {
            "tables":        tables,
            "relationships": _relationships_from_tables(tables),
        }

    # ── Single-table fallback ────────────────────────────────────────────────
    # Try to find an explicit table name — exclude common verbs/stop-words that
    # appear after "entity" in natural sentences (e.g. "customer entity has multiple…"
    # must NOT produce table_name="has").
    _TABLE_NAME_STOP = {
        "has", "is", "are", "was", "were", "have", "had", "be", "been",
        "do", "does", "did", "will", "would", "should", "could", "can",
        "the", "a", "an", "of", "for", "with", "to", "and", "or", "that",
        "which", "multiple", "some", "many", "several", "each", "any",
    }
    table_match = re.search(
        r"(?:table|entity|sheet|dataset)\s+(?:called|named|:)?\s*['\"]?(\w+)['\"]?",
        text, re.I,
    )
    if table_match and table_match.group(1).lower() in _TABLE_NAME_STOP:
        table_match = None
    table_name = table_match.group(1) if table_match else "dataset"

    # Extract field names from "columns: ..." or "fields: ..." patterns
    field_match = re.search(
        r"(?:columns?|fields?|attributes?)\s*[:\-]?\s*(.+?)(?:\.|$)",
        text, re.I | re.DOTALL,
    )
    if field_match:
        names = _parse_field_list(field_match.group(1))
    else:
        # Fallback: find quoted words or snake_case identifiers that look like field names
        raw_pairs = re.findall(
            r"['\"]([a-zA-Z_][a-zA-Z0-9_]{1,40})['\"]"
            r"|(?<!\w)([a-z][a-z0-9_]{1,30}_(?:id|name|date|at|status|type|code|no|num|amount|total|count))",
            text,
        )
        names = [a or b for a, b in raw_pairs if (a or b)]

    if not names:
        names = ["id", "name", "description", "status", "created_at"]

    return {
        "tables": [
            {
                "table_name": table_name,
                "filename":   None,
                "columns":    [_make_col(n) for n in names],
                "row_count":  0,
            }
        ],
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
                                "source_table": t2["table_name"],
                                "source_column": c2["name"],
                                "target_table": t1["table_name"],
                                "target_column": c1["name"],
                                "cardinality": "one_to_many",
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
