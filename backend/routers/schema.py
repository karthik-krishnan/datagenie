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
from services.compliance_detector import detect_compliance, detect_domain_frameworks, FRAMEWORK_RECOMMENDATIONS
from services.context_extractor import extract_from_context
from services.llm_service import get_provider

router = APIRouter()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _get_llm_provider(db: AsyncSession):
    """Load current LLM settings from DB and return a provider instance."""
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
    db: AsyncSession = Depends(get_db),
):
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

    # --- Demo mode: skip all parsing, return a pre-built template ---
    llm_provider = await _get_llm_provider(db)
    from services.llm_service import DemoProvider
    if isinstance(llm_provider, DemoProvider) and not parsed_files:
        from services.demo_templates import get_demo_schema
        return get_demo_schema(context_text)

    # --- Detect domain frameworks from the context text first ---
    # This tells us if the user is in a healthcare, payments, EU/GDPR context etc.
    domain_frameworks = detect_domain_frameworks(context_text)

    # --- Schema inference from files ---
    schema = infer_schema(parsed_files, context_text)

    # --- Compliance detection on all columns (multi-framework aware) ---
    sensitive_detected = False
    all_frameworks_detected: set = set()
    for table in schema["tables"]:
        for col in table["columns"]:
            sample = col.get("sample_values", [])
            compliance = detect_compliance(col["name"], sample, domain_frameworks)
            col["pii"] = compliance   # keeping key name "pii" for frontend compatibility
            if compliance["is_sensitive"]:
                sensitive_detected = True
                all_frameworks_detected.update(compliance["frameworks"])

    # --- Extract structured params from context text (+ file column context) ---
    combined_context = context_text.strip()
    if parsed_files and combined_context:
        file_col_summary = "; ".join(
            f"{pf['table_name']}: {', '.join(c['name'] for c in pf['columns'])}"
            for pf in parsed_files
        )
        combined_context = (
            f"{combined_context}\n\n[Detected columns from uploaded files: {file_col_summary}]"
        )

    extracted = extract_from_context(combined_context or context_text, llm_provider)

    # --- Merge: compliance rules extracted from text → update schema columns ---
    for col_name, rule in extracted.get("compliance_rules", {}).items():
        if rule.get("pii_type"):
            sensitive_detected = True
            for table in schema["tables"]:
                for col in table["columns"]:
                    if col["name"].lower() == col_name.lower():
                        if not col["pii"]["is_sensitive"]:
                            # Re-run detection so domain context is applied
                            compliance = detect_compliance(col_name, [], domain_frameworks)
                            col["pii"] = compliance
                            all_frameworks_detected.update(compliance["frameworks"])

    # --- Context-only mode: build schema from extracted columns ---
    if not parsed_files and extracted.get("columns"):
        entity_type = extracted.get("entity_type", "records")
        cols = []
        for c in extracted["columns"]:
            name = c.get("name", "")
            if not name:
                continue
            compliance = detect_compliance(name, [], domain_frameworks)
            # Override with explicit compliance rules from context if present
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

    schema["pii_detected"] = sensitive_detected        # kept for backward compat
    schema["sensitive_detected"] = sensitive_detected
    schema["frameworks_detected"] = sorted(all_frameworks_detected)
    schema["domain_frameworks"] = sorted(domain_frameworks)
    schema["context"] = context_text
    schema["extracted"] = extracted

    try:
        await db.commit()
    except Exception:
        await db.rollback()

    return schema
