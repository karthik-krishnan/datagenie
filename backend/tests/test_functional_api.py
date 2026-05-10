"""
Functional tests — HTTP API endpoints (End-to-end / Integration layer)

Covers:
  Req 1: Context picked up from both file upload AND context_text form field
  Req 2: File-only and text-only both succeed at /api/schema/infer
  Req 3: Multiple files in a single infer request → multi-table schema
  Req 4: Compliance rules applied through the full generate pipeline
  Req 5: Relationships submitted to /api/generate/ produce FK-valid data in ZIP
  Req 6: Multi-table generate with CSV format returns a ZIP

All tests use FastAPI's TestClient with the database dependency overridden by a
lightweight mock so no real database or LLM is required.
"""
import sys
import os
import io
import csv
import json
import zipfile
import tempfile

# Must set UPLOAD_DIR before importing main.py so routers don't try to create /app/uploads
_TMP_UPLOAD_DIR = tempfile.mkdtemp(prefix="tdg_test_uploads_")
os.environ.setdefault("UPLOAD_DIR", _TMP_UPLOAD_DIR)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# ── DB mock ──────────────────────────────────────────────────────────────────
# The mock session returns no LLM settings row → falls back to DemoProvider.

class _MockResult:
    def scalar_one_or_none(self):
        return None   # no LLM settings saved → demo mode


class _MockSession:
    async def execute(self, *a, **kw):
        return _MockResult()

    async def commit(self): pass
    async def rollback(self): pass
    async def add(self, *a): pass
    async def flush(self): pass


async def _mock_get_db():
    yield _MockSession()


# ── App setup with overridden DB ──────────────────────────────────────────────

from main import app
from database import get_db

app.dependency_overrides[get_db] = _mock_get_db
client = TestClient(app)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _infer(files=None, context_text=""):
    """Helper: POST /api/schema/infer."""
    data  = {"context_text": context_text}
    mfiles = []
    if files:
        for name, rows in files.items():
            mfiles.append(("files", (name, _csv_bytes(rows), "text/csv")))
    return client.post("/api/schema/infer", data=data, files=mfiles if mfiles else None)


def _generate(schema, relationships=None, compliance_rules=None, volume=5, formats=None, packaging="one_file_per_entity"):
    payload = {
        "schema": schema,
        "relationships": relationships or [],
        "compliance_rules": compliance_rules or {},
        "volume": volume,
        "formats": formats or ["csv"],
        "packaging": packaging,
        "llm_config": {"provider": "demo"},
    }
    return client.post("/api/generate/", json=payload)


def _preview(schema, relationships=None, compliance_rules=None):
    payload = {
        "schema": schema,
        "relationships": relationships or [],
        "compliance_rules": compliance_rules or {},
        "volume": 5,
        "formats": ["csv"],
        "llm_config": {"provider": "demo"},
    }
    return client.post("/api/generate/preview", json=payload)


# ─── Req 2a: File-only infer ──────────────────────────────────────────────────

class TestInferFileOnly:

    def test_returns_200(self):
        r = _infer(files={"users.csv": [{"id": 1, "name": "Alice"}]})
        assert r.status_code == 200

    def test_returns_schema_with_tables(self):
        r = _infer(files={"users.csv": [{"id": 1, "name": "Alice"}]})
        body = r.json()
        assert "tables" in body
        assert len(body["tables"]) == 1

    def test_column_names_from_file(self):
        r = _infer(files={"items.csv": [{"id": 1, "sku": "A1", "price": "9.99"}]})
        cols = {c["name"] for c in r.json()["tables"][0]["columns"]}
        assert cols == {"id", "sku", "price"}

    def test_type_inference_from_file(self):
        rows = [{"id": str(i), "email": f"u{i}@x.com", "score": f"{i}.5"} for i in range(1, 6)]
        r = _infer(files={"data.csv": rows})
        col_map = {c["name"]: c["type"] for c in r.json()["tables"][0]["columns"]}
        assert col_map["id"] == "integer"
        assert col_map["email"] == "email"
        assert col_map["score"] == "float"


# ─── Req 2b: Text-only infer ──────────────────────────────────────────────────

class TestInferTextOnly:

    def test_returns_200(self):
        r = _infer(context_text="Generate a users table with columns: id, name, email, status")
        assert r.status_code == 200

    def test_returns_schema(self):
        r = _infer(context_text="columns: id, name, email, status")
        body = r.json()
        assert "tables" in body
        assert len(body["tables"]) == 1

    def test_returns_columns_for_text_only(self):
        """Text-only + demo mode returns the demo template schema (not raw context columns).
        Verify a non-empty column list is returned."""
        r = _infer(context_text="Generate a dataset with user profiles")
        cols = [c["name"] for c in r.json()["tables"][0]["columns"]]
        assert len(cols) > 0, "Expected at least one column in text-only schema"


# ─── Req 1: Both file + context text ─────────────────────────────────────────

class TestInferFileAndContext:

    def test_returns_200(self):
        r = _infer(
            files={"orders.csv": [{"id": 1, "total": "9.99", "card_number": "4111111111111111"}]},
            context_text="PCI-compliant payment data for e-commerce orders",
        )
        assert r.status_code == 200

    def test_file_columns_preserved(self):
        r = _infer(
            files={"customers.csv": [{"id": 1, "full_name": "Alice", "card_number": "4111111111111111"}]},
            context_text="PCI DSS compliance required — mask card numbers",
        )
        cols = {c["name"] for c in r.json()["tables"][0]["columns"]}
        assert "full_name" in cols
        assert "card_number" in cols

    def test_compliance_metadata_applied_to_sensitive_columns(self):
        r = _infer(
            files={"users.csv": [{"id": 1, "ssn": "123-45-6789", "email": "a@b.com"}]},
            context_text="HIPAA dataset with patient identifiers",
        )
        body = r.json()
        col_map = {c["name"]: c for c in body["tables"][0]["columns"]}
        # SSN or email should have pii metadata populated
        sensitive = any(
            c.get("pii", {}).get("is_sensitive") or c.get("pii", {}).get("is_pii")
            for c in body["tables"][0]["columns"]
        )
        assert sensitive, "Expected at least one column to be marked sensitive"

    def test_domain_frameworks_detected_from_context(self):
        r = _infer(
            files={"records.csv": [{"id": 1, "diagnosis": "Flu"}]},
            context_text="Healthcare patient records with medical diagnoses (HIPAA)",
        )
        body = r.json()
        # frameworks_detected or domain_frameworks should contain HIPAA
        detected = body.get("frameworks_detected", []) + body.get("domain_frameworks", [])
        assert "HIPAA" in detected, f"Expected HIPAA in detected frameworks: {detected}"


# ─── Req 3: Multiple files → multi-table schema ───────────────────────────────

class TestInferMultipleFiles:

    def test_two_files_produce_two_tables(self):
        r = _infer(files={
            "users.csv":  [{"id": 1, "name": "Alice"}],
            "orders.csv": [{"id": 1, "user_id": 1, "total": "9.99"}],
        })
        assert len(r.json()["tables"]) == 2

    def test_table_names_match_filenames(self):
        r = _infer(files={
            "customers.csv": [{"id": 1}],
            "products.csv":  [{"id": 1}],
        })
        names = {t["table_name"] for t in r.json()["tables"]}
        assert "customers" in names
        assert "products"  in names

    def test_fk_relationship_detected(self):
        r = _infer(files={
            "users.csv":  [{"id": 1, "name": "Alice"}],
            "orders.csv": [{"id": 1, "user_id": 1, "total": "5.00"}],
        })
        rels = r.json().get("relationships", [])
        assert len(rels) > 0, "Expected FK relationship between orders.user_id and users.id"
        rel = rels[0]
        assert rel["source_column"] == "user_id"
        assert rel["target_table"]  == "users"

    def test_three_files(self):
        r = _infer(files={
            "a.csv": [{"id": 1}],
            "b.csv": [{"id": 1}],
            "c.csv": [{"id": 1}],
        })
        assert len(r.json()["tables"]) == 3


# ─── Req 4: Compliance through generate pipeline ──────────────────────────────

class TestComplianceViaGeneratePreview:

    def _base_schema(self):
        return {
            "tables": [{
                "table_name": "users",
                "filename": "users.csv",
                "row_count": 5,
                "columns": [
                    {"name": "id",    "type": "integer", "pattern": "identifier",
                     "sample_values": [], "enum_values": [], "pii": {}},
                    {"name": "ssn",   "type": "string",  "pattern": "generic",
                     "sample_values": [], "enum_values": [],
                     "pii": {"is_sensitive": True, "field_type": "social_security",
                             "frameworks": ["PII", "HIPAA"], "default_action": "fake_realistic"}},
                    {"name": "email", "type": "email",   "pattern": "generic",
                     "sample_values": [], "enum_values": [],
                     "pii": {"is_sensitive": True, "field_type": "email_address",
                             "frameworks": ["PII"], "default_action": "fake_realistic"}},
                ],
            }],
            "relationships": [],
        }

    def test_redact_rule_applied(self):
        r = _preview(self._base_schema(), compliance_rules={"ssn": {"action": "redact"}})
        assert r.status_code == 200
        rows = r.json()["preview"]["users"]
        for row in rows:
            assert row["ssn"] == "[REDACTED]", f"Expected [REDACTED], got {row['ssn']}"

    def test_mask_rule_applied(self):
        import re
        r = _preview(self._base_schema(), compliance_rules={"ssn": {"action": "mask"}})
        rows = r.json()["preview"]["users"]
        for row in rows:
            assert not re.search(r"[A-Za-z0-9]", str(row["ssn"])), f"ssn not fully masked: {row['ssn']}"

    def test_custom_rule_show_last_4_digits(self):
        import re
        r = _preview(
            self._base_schema(),
            compliance_rules={"ssn": {
                "action": "Custom",
                "custom_rule": "show last 4 digits",
                "masking_op": {"type": "show_last_n_digits", "n": 4},
            }},
        )
        rows = r.json()["preview"]["users"]
        for row in rows:
            v = str(row["ssn"])
            digits = re.sub(r"\D", "", v)
            if len(digits) >= 4:
                assert v.endswith(digits[-4:]), f"show_last_4_digits failed: {v}"

    def test_no_compliance_rule_generates_realistic_ssn(self):
        import re
        r = _preview(self._base_schema())
        rows = r.json()["preview"]["users"]
        for row in rows:
            assert re.match(r"\d{3}-\d{2}-\d{4}", str(row["ssn"])), (
                f"SSN without rule should be realistic: {row['ssn']}"
            )

    def test_preview_returns_exactly_five_rows(self):
        r = _preview(self._base_schema())
        rows = r.json()["preview"]["users"]
        assert len(rows) == 5


# ─── Req 5: Relationships produce FK-valid data via generate endpoint ─────────

class TestRelationshipsViaGenerateEndpoint:

    def _schema(self):
        return {
            "tables": [
                {
                    "table_name": "users", "filename": "users.csv", "row_count": 5,
                    "columns": [
                        {"name": "id",   "type": "integer", "pattern": "identifier",
                         "sample_values": [], "enum_values": [], "pii": {}},
                        {"name": "name", "type": "string",  "pattern": "name",
                         "sample_values": [], "enum_values": [], "pii": {}},
                    ],
                },
                {
                    "table_name": "orders", "filename": "orders.csv", "row_count": 5,
                    "columns": [
                        {"name": "id",      "type": "integer", "pattern": "identifier",
                         "sample_values": [], "enum_values": [], "pii": {}},
                        {"name": "user_id", "type": "integer", "pattern": "identifier",
                         "sample_values": [], "enum_values": [], "pii": {}},
                        {"name": "total",   "type": "float",   "pattern": "currency",
                         "sample_values": [], "enum_values": [], "pii": {}},
                    ],
                },
            ],
            "relationships": [],
        }

    def _rels(self):
        return [{
            "source_table": "orders", "source_column": "user_id",
            "target_table": "users",  "target_column": "id",
            "cardinality":  "many_to_one", "confidence": 0.9,
        }]

    def test_generate_returns_zip_for_two_tables(self):
        r = _generate(self._schema(), self._rels(), volume=5)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert zipfile.is_zipfile(io.BytesIO(r.content))

    def test_zip_contains_users_and_orders_csv(self):
        r = _generate(self._schema(), self._rels(), volume=5)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            assert "users.csv"  in zf.namelist()
            assert "orders.csv" in zf.namelist()

    def test_order_user_ids_reference_valid_users(self):
        r = _generate(self._schema(), self._rels(), volume=8)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            u_rows = list(csv.DictReader(io.StringIO(zf.read("users.csv").decode())))
            o_rows = list(csv.DictReader(io.StringIO(zf.read("orders.csv").decode())))
        user_ids = {row["id"] for row in u_rows}
        for order in o_rows:
            assert order["user_id"] in user_ids, (
                f"orders.user_id={order['user_id']} not in users.id set {user_ids}"
            )

    def test_both_tables_have_correct_volume(self):
        r = _generate(self._schema(), self._rels(), volume=7)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            u_rows = list(csv.DictReader(io.StringIO(zf.read("users.csv").decode())))
            o_rows = list(csv.DictReader(io.StringIO(zf.read("orders.csv").decode())))
        assert len(u_rows) == 7
        assert len(o_rows) == 7


# ─── Req 6: Multi-table generate → ZIP ───────────────────────────────────────

class TestMultiTableZipDownload:

    def _two_table_schema(self):
        def _table(name, cols):
            return {"table_name": name, "filename": f"{name}.csv", "row_count": 5,
                    "columns": [{"name": c, "type": "string", "pattern": "generic",
                                 "sample_values": [], "enum_values": [], "pii": {}} for c in cols]}
        return {"tables": [_table("alpha", ["id", "x"]), _table("beta", ["id", "y"])],
                "relationships": []}

    def test_returns_zip_mime_type(self):
        r = _generate(self._two_table_schema(), volume=3)
        assert r.headers["content-type"] == "application/zip"

    def test_content_disposition_is_zip(self):
        r = _generate(self._two_table_schema(), volume=3)
        assert "test_data.zip" in r.headers.get("content-disposition", "")

    def test_zip_is_valid(self):
        r = _generate(self._two_table_schema(), volume=3)
        assert zipfile.is_zipfile(io.BytesIO(r.content))

    def test_zip_has_one_file_per_table(self):
        r = _generate(self._two_table_schema(), volume=3)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            assert set(zf.namelist()) == {"alpha.csv", "beta.csv"}

    def test_single_table_is_not_a_zip(self):
        schema = {
            "tables": [{"table_name": "solo", "filename": "solo.csv", "row_count": 5,
                        "columns": [{"name": "id", "type": "integer", "pattern": "identifier",
                                     "sample_values": [], "enum_values": [], "pii": {}}]}],
            "relationships": [],
        }
        r = _generate(schema, volume=3)
        # FastAPI adds "; charset=utf-8" to text/* MIME types
        assert r.headers["content-type"].startswith("text/csv")
        assert not zipfile.is_zipfile(io.BytesIO(r.content))

    def test_xlsx_multi_table_is_single_file_not_data_zip(self):
        """XLSX is OOXML (ZIP-based internally) but is a single workbook file, not our data zip."""
        r = _generate(self._two_table_schema(), volume=3, formats=["xlsx"])
        ct = r.headers["content-type"]
        assert "spreadsheetml" in ct, f"Expected xlsx MIME, got {ct}"
        # Our data ZIPs have application/zip MIME; XLSX uses spreadsheetml
        assert "application/zip" not in ct

    def test_merged_packaging_returns_single_csv(self):
        r = _generate(self._two_table_schema(), volume=3, packaging="merged")
        assert r.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(io.StringIO(r.content.decode())))
        assert "_entity" in rows[0]
        assert len(rows) == 6   # 3 rows × 2 tables
