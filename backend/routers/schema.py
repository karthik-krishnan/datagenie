import os
import json
import uuid as _uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
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
    files: Optional[List[UploadFile]] = File(default=None),
    context_text: str = Form(""),
    session_id: Optional[str] = Form(None),
    # LLM config from browser localStorage — optional, takes priority over DB
    llm_provider: Optional[str] = Form(None),
    llm_api_key: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
    llm_extra_config: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # Build override dict from request params if provided
    llm_override = None
    if llm_provider:
        extra_cfg = {}
        if llm_extra_config:
            try:
                extra_cfg = json.loads(llm_extra_config)
            except Exception:
                pass
        llm_override = {
            "provider": llm_provider,
            "api_key": llm_api_key or "",
            "model": llm_model or "",
            "extra_config": extra_cfg,
        }

    parsed_files = []
    for f in (files or []):
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
    from services.llm_service import DemoProvider, AzureOpenAIProvider
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

    # --- Schema inference from files ---
    schema = infer_schema(parsed_files, context_text)

    # --- Compliance detection on all columns (multi-framework aware) ---
    sensitive_detected = False
    all_frameworks_detected: set = set()

    # Gather all columns for one-shot LLM classification
    all_cols_for_llm = [
        {"name": col["name"], "sample_values": col.get("sample_values", [])}
        for table in schema["tables"]
        for col in table["columns"]
    ]

    # LLM batch classification with validation + retry (skipped for DemoProvider)
    llm_batch = detect_compliance_batch_llm(
        all_cols_for_llm, llm_provider_obj, context_text, domain_frameworks
    )
    llm_compliance = llm_batch["results"]
    if llm_batch["warning"] and not llm_warning:
        llm_warning = llm_batch["warning"]

    for table in schema["tables"]:
        for col in table["columns"]:
            sample = col.get("sample_values", [])
            # Prefer LLM result; fall back to deterministic catalog / value-pattern matching
            compliance = (
                llm_compliance.get(col["name"])
                or detect_compliance(col["name"], sample, domain_frameworks)
            )
            col["pii"] = compliance
            if compliance["is_sensitive"]:
                sensitive_detected = True
                all_frameworks_detected.update(compliance["frameworks"])

    # --- Extract structured params from context text ---
    combined_context = context_text.strip()
    if parsed_files and combined_context:
        file_col_summary = "; ".join(
            f"{pf['table_name']}: {', '.join(c['name'] for c in pf['columns'])}"
            for pf in parsed_files
        )
        combined_context = (
            f"{combined_context}\n\n[Detected columns from uploaded files: {file_col_summary}]"
        )

    extracted = extract_from_context(combined_context or context_text, llm_provider_obj)

    # --- Merge compliance rules extracted from text → update schema columns ---
    for col_name, rule in extracted.get("compliance_rules", {}).items():
        if rule.get("pii_type"):
            sensitive_detected = True
            for table in schema["tables"]:
                for col in table["columns"]:
                    if col["name"].lower() == col_name.lower():
                        if not col["pii"]["is_sensitive"]:
                            compliance = detect_compliance(col_name, [], domain_frameworks)
                            col["pii"] = compliance
                            all_frameworks_detected.update(compliance["frameworks"])

    # --- Context-only mode: build schema from extracted columns ---
    # Only apply this single-entity override when _infer_schema_from_context did NOT
    # already produce a multi-table schema (i.e. schema has exactly one generic table).
    _context_only_single = (
        not parsed_files
        and extracted.get("columns")
        and len(schema.get("tables", [])) == 1
        and schema["tables"][0].get("table_name") in ("dataset", extracted.get("entity_type", ""))
    )
    if _context_only_single:
        entity_type = extracted.get("entity_type", "records")

        # Run LLM batch compliance on the extracted column list (with retry)
        extracted_col_dicts = [
            {"name": c.get("name", ""), "sample_values": []}
            for c in extracted["columns"] if c.get("name")
        ]
        llm_ctx_batch = detect_compliance_batch_llm(
            extracted_col_dicts, llm_provider_obj, context_text, domain_frameworks
        )
        llm_compliance_ctx = llm_ctx_batch["results"]
        if llm_ctx_batch["warning"] and not llm_warning:
            llm_warning = llm_ctx_batch["warning"]

        cols = []
        for c in extracted["columns"]:
            name = c.get("name", "")
            if not name:
                continue
            # LLM result preferred; catalog/pattern fallback
            compliance = (
                llm_compliance_ctx.get(name)
                or detect_compliance(name, [], domain_frameworks)
            )
            cr = extracted.get("compliance_rules", {}).get(name)
            if cr and cr.get("pii_type") and not compliance["is_sensitive"]:
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
        schema = {
            "tables": [{
                "table_name": entity_type,
                "filename": None,
                "columns": cols,
                "row_count": 0,
            }],
            "relationships": [],
        }

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
