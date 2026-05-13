import os
import json
import uuid as _uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import UploadedFile as UploadedFileModel, LLMSettings as LLMSettingsModel
from services.file_parser import parse_file
from services.schema_inferrer import infer_schema
from services.compliance_detector import (
    detect_compliance,
    detect_compliance_batch_llm,
    detect_domain_frameworks,
    FRAMEWORK_RECOMMENDATIONS,
)
from services.context_extractor import extract_from_context
from services.llm_service import get_provider
from services.masking import normalize_masking_rule

router = APIRouter()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _get_llm_provider(db: AsyncSession, override: dict = None):
    """Return a provider instance. Uses the frontend-supplied override first (localStorage key),
    falls back to DB for self-hosted deployments, then falls back to Demo."""
    if override and override.get("provider") and override["provider"] != "demo":
        try:
            return get_provider(override)
        except Exception:
            pass
    try:
        result = await db.execute(
            select(LLMSettingsModel).order_by(LLMSettingsModel.id.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return get_provider({"provider": "demo"})
        settings = {
            "provider": row.provider,
            "api_key": row.api_key,
            "model": row.model,
            "extra_config": json.loads(row.extra_config or "{}"),
        }
        return get_provider(settings)
    except Exception:
        return get_provider({"provider": "demo"})


@router.post("/infer")
async def infer(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Parse multipart form manually — avoids Pydantic v2 single-file coercion bug
    # where List[UploadFile] rejects a single uploaded file as "not a valid list".
    form = await request.form()
    raw_files = form.getlist("files")
    # getlist returns [] when absent; a single file comes as a 1-item list
    if not isinstance(raw_files, list):
        raw_files = [raw_files] if raw_files else []

    context_text  = form.get("context_text", "") or ""
    session_id    = form.get("session_id")
    llm_provider  = form.get("llm_provider")
    llm_api_key   = form.get("llm_api_key", "")
    llm_model     = form.get("llm_model", "")
    llm_extra_config = form.get("llm_extra_config", "{}")

    # Build override dict from request params if provided
    llm_override = None
    if llm_provider:
        extra_cfg = {}
        try:
            extra_cfg = json.loads(llm_extra_config or "{}")
        except Exception:
            pass
        llm_override = {
            "provider": llm_provider,
            "api_key": llm_api_key or "",
            "model": llm_model or "",
            "extra_config": extra_cfg,
        }

    parsed_files = []
    for f in raw_files:
        ext = (f.filename.split(".")[-1] or "").lower()
        path = os.path.join(UPLOAD_DIR, f"{_uuid.uuid4()}_{f.filename}")
        content = await f.read()
        with open(path, "wb") as out:
            out.write(content)
        try:
            parsed = parse_file(path, ext)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse {f.filename}: {e}")
        table_name = os.path.splitext(f.filename)[0]
        parsed_files.append({
            "filename": f.filename,
            "table_name": table_name,
            "extension": ext,
            "rows": parsed["rows"],
            "columns": parsed["columns"],
        })

        if session_id:
            try:
                rec = UploadedFileModel(
                    session_id=_uuid.UUID(session_id),
                    filename=f.filename,
                    file_type=ext,
                    parsed_schema=json.dumps({"columns": parsed["columns"]}),
                )
                db.add(rec)
            except Exception:
                pass

    # --- Resolve LLM provider (override from browser > DB > demo fallback) ---
    llm_provider_obj = await _get_llm_provider(db, llm_override)

    # --- Validate provider config early — surface clear errors for misconfigured providers ---
    from services.llm_service import AzureOpenAIProvider
    llm_warning: str | None = None
    if isinstance(llm_provider_obj, AzureOpenAIProvider):
        if not llm_provider_obj.endpoint:
            llm_warning = ("Azure OpenAI endpoint is not configured. "
                           "Open Settings and add 'endpoint' to Extra Config (e.g. "
                           "https://your-resource.openai.azure.com/).")
        elif not llm_provider_obj.deployment:
            llm_warning = ("Azure OpenAI deployment name is not configured. "
                           "Open Settings and add 'deployment' to Extra Config.")

    # --- Detect domain frameworks from the context text first ---
    domain_frameworks = detect_domain_frameworks(context_text)

    sensitive_detected = False
    all_frameworks_detected: set = set()

    # -------------------------------------------------------------------------
    # TWO PATHS: context-only vs file-based
    # -------------------------------------------------------------------------

    if not parsed_files:
        # --- CONTEXT-ONLY: LLM does everything — no regex, no infer_schema ---
        extracted = extract_from_context(context_text, llm_provider_obj)

        def _build_cols_with_compliance(columns, compliance_rules):
            """Build enriched column list with LLM compliance detection."""
            nonlocal sensitive_detected, all_frameworks_detected
            col_dicts = [{"name": c.get("name", ""), "sample_values": []} for c in columns if c.get("name")]
            batch = detect_compliance_batch_llm(col_dicts, llm_provider_obj, context_text, domain_frameworks)
            if batch["warning"] and not llm_warning:
                pass  # warning surfaced below per-table
            llm_comp = batch["results"]
            cols = []
            for c in columns:
                name = c.get("name", "")
                if not name:
                    continue
                compliance = llm_comp.get(name) or detect_compliance(name, [], domain_frameworks)
                cr = compliance_rules.get(name, {})
                if cr.get("pii_type") and not compliance["is_sensitive"]:
                    compliance = {
                        "is_sensitive": True,
                        "frameworks": [cr["pii_type"]],
                        "field_type": name,
                        "default_action": "fake_realistic",
                        "recommendations": {cr["pii_type"]: FRAMEWORK_RECOMMENDATIONS.get(cr["pii_type"], "")},
                        "confidence": 0.9,
                    }
                if compliance["is_sensitive"]:
                    sensitive_detected = True
                    all_frameworks_detected.update(compliance["frameworks"])
                cols.append({
                    "name": name,
                    "type": c.get("type", "string"),
                    "sample_values": [],
                    "pattern": name,
                    "enum_values": c.get("enum_values", []),
                    "pii": compliance,
                })
            return cols, batch["warning"]

        compliance_rules = extracted.get("compliance_rules", {})

        if extracted.get("tables") and len(extracted["tables"]) > 1:
            # Multi-table schema
            schema = {"tables": [], "relationships": []}
            for tbl in extracted["tables"]:
                cols, warn = _build_cols_with_compliance(tbl.get("columns", []), compliance_rules)
                if warn and not llm_warning:
                    llm_warning = warn
                is_root = tbl.get("is_root", False)
                schema["tables"].append({
                    "table_name": tbl.get("name", "records"),
                    "filename": None,
                    "columns": cols,
                    "row_count": (extracted.get("volume") or 0) if is_root else 0,
                    "is_root": is_root,
                })
            for rel in extracted.get("relationships", []):
                per_min = rel.get("per_parent_min")
                per_max = rel.get("per_parent_max")
                schema["relationships"].append({
                    "source_table": rel.get("source_table", ""),
                    "target_table": rel.get("target_table", ""),
                    "cardinality": "one_to_many",
                    "per_parent": {"min": per_min, "max": per_max, "shape": "Uniform"} if (per_min is not None or per_max is not None) else None,
                })
        else:
            # Single-table schema
            columns = extracted.get("columns") or []
            # In demo mode the LLM is unavailable so _regex_fallback runs inside
            # extract_from_context. If it still returns no columns, use a hardcoded
            # default set rather than treating an empty LLM result as needing a fallback.
            if not columns and llm_provider_obj.is_demo:
                from services.schema_inferrer import _infer_schema_from_context
                fallback = _infer_schema_from_context(context_text)
                columns = [{"name": c["name"], "type": c.get("type", "string"), "enum_values": c.get("enum_values", [])} for c in fallback["tables"][0]["columns"]]
            cols, warn = _build_cols_with_compliance(columns, compliance_rules)
            if warn and not llm_warning:
                llm_warning = warn
            schema = {
                "tables": [{
                    "table_name": extracted.get("entity_type", "records"),
                    "filename": None,
                    "columns": cols,
                    "row_count": 0,
                }],
                "relationships": [],
            }

    else:
        # --- FILE-BASED: infer schema from uploaded files, then run compliance ---
        schema = infer_schema(parsed_files, context_text)

        all_cols_for_llm = [
            {"name": col["name"], "sample_values": col.get("sample_values", [])}
            for table in schema["tables"]
            for col in table["columns"]
        ]
        llm_batch = detect_compliance_batch_llm(
            all_cols_for_llm, llm_provider_obj, context_text, domain_frameworks
        )
        llm_compliance = llm_batch["results"]
        if llm_batch["warning"] and not llm_warning:
            llm_warning = llm_batch["warning"]

        for table in schema["tables"]:
            for col in table["columns"]:
                compliance = (
                    llm_compliance.get(col["name"])
                    or detect_compliance(col["name"], col.get("sample_values", []), domain_frameworks)
                )
                col["pii"] = compliance
                if compliance["is_sensitive"]:
                    sensitive_detected = True
                    all_frameworks_detected.update(compliance["frameworks"])

        # Augment with any extra context the user typed alongside the files
        combined_context = context_text.strip()
        if combined_context:
            file_col_summary = "; ".join(
                f"{pf['table_name']}: {', '.join(c['name'] for c in pf['columns'])}"
                for pf in parsed_files
            )
            combined_context = (
                f"{combined_context}\n\n[Detected columns from uploaded files: {file_col_summary}]"
            )
        extracted = extract_from_context(combined_context or context_text, llm_provider_obj)

        # Merge any compliance rules the LLM identified from the context text
        for col_name, rule in extracted.get("compliance_rules", {}).items():
            if rule.get("pii_type"):
                sensitive_detected = True
                for table in schema["tables"]:
                    for col in table["columns"]:
                        if col["name"].lower() == col_name.lower() and not col["pii"]["is_sensitive"]:
                            compliance = detect_compliance(col_name, [], domain_frameworks)
                            col["pii"] = compliance
                            all_frameworks_detected.update(compliance["frameworks"])

    schema["pii_detected"] = sensitive_detected
    schema["sensitive_detected"] = sensitive_detected
    schema["frameworks_detected"] = sorted(all_frameworks_detected)
    schema["domain_frameworks"] = sorted(domain_frameworks)
    schema["context"] = context_text
    schema["extracted"] = extracted
    schema["llm_warning"] = llm_warning  # None when all OK; string when provider misconfigured

    try:
        await db.commit()
    except Exception:
        await db.rollback()

    return schema


# ---------------------------------------------------------------------------
# Normalise a plain-English masking rule → structured MaskingOp
# Called by the frontend whenever a user types a custom compliance rule.
# ---------------------------------------------------------------------------
# Demo template endpoint — always returns the built-in template regardless
# of the user's LLM settings.  Used by the ProfilePicker starter cards so
# clicking a card is fast, deterministic, and works even with a real LLM.
# ---------------------------------------------------------------------------

@router.get("/demo")
async def get_demo(keyword: str = ""):
    """
    GET /api/schema/demo?keyword=<text>
    Returns the best-matching demo template for the given keyword(s).
    Never calls any LLM — purely the built-in canned schema.
    """
    from services.demo_templates import get_demo_schema
    return get_demo_schema(keyword)


# ---------------------------------------------------------------------------
class _NormaliseRuleRequest(dict):
    """Thin wrapper — FastAPI reads the JSON body as a plain dict."""


@router.post("/normalize-rule")
async def normalize_rule(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/schema/normalize-rule
    Body: {"rule": "<plain-text masking instruction>", "llm_provider": "...", ...}
    Returns: {"masking_op": {...} | null, "rule": "<original text>"}

    The frontend calls this when the user saves a custom compliance rule so the
    structured op is stored alongside the text and generation stays deterministic.
    """
    rule_text = (body.get("rule") or "").strip()
    if not rule_text:
        return {"masking_op": None, "rule": rule_text}

    # Build LLM provider from body or DB / demo fallback
    llm_override = None
    if body.get("llm_provider"):
        llm_override = {
            "provider": body.get("llm_provider", "demo"),
            "api_key": body.get("llm_api_key", ""),
            "model": body.get("llm_model", ""),
            "extra_config": body.get("llm_extra_config", {}),
        }
    provider = await _get_llm_provider(db, llm_override)

    op = normalize_masking_rule(rule_text, provider)
    return {"masking_op": op, "rule": rule_text}
