"""
Functional tests — Schema Inference (Requirement 1, 2, 3)

Covers:
  1. Context picked up from BOTH uploaded files AND free-text description
  2. File-only mode (no context text) still works
  3. Text-only mode (no files) still works
  4. Multiple uploaded files produce multi-table schema
  5. Relationship / FK detection between tables

These tests call the service layer directly so they run without a database
or live LLM (all compliance detection falls back to the catalog/pattern path).
"""
import sys
import os
import io
import tempfile
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.schema_inferrer import infer_schema
from services.file_parser import parse_file


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_csv(rows: list[dict], tmp_dir: str, name: str = "data.csv") -> dict:
    """Write rows to a CSV file, parse it, and return the parsed_file dict."""
    path = os.path.join(tmp_dir, name)
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("id,name\n")
    parsed = parse_file(path, "csv")
    parsed["table_name"] = name.replace(".csv", "")
    parsed["filename"] = name
    return parsed


# ─── Requirement 2a: File-only (no context text) ─────────────────────────────

class TestFileOnlyMode:

    def test_single_file_produces_one_table(self, tmp_path):
        rows = [{"id": 1, "name": "Alice", "email": "alice@example.com"}]
        pf = _make_csv(rows, str(tmp_path), "users.csv")
        schema = infer_schema([pf])
        assert len(schema["tables"]) == 1
        assert schema["tables"][0]["table_name"] == "users"

    def test_column_types_inferred_from_file(self, tmp_path):
        # Use MM/DD/YYYY format — avoids false phone-regex match on YYYY-MM-DD
        rows = [
            {"id": "1", "email": "a@b.com", "score": "3.5", "active": "true", "joined": "01/15/2024"},
            {"id": "2", "email": "c@d.com", "score": "7.2", "active": "false", "joined": "02/20/2024"},
        ]
        pf = _make_csv(rows, str(tmp_path), "users.csv")
        schema = infer_schema([pf])
        col_map = {c["name"]: c["type"] for c in schema["tables"][0]["columns"]}
        assert col_map["id"] == "integer"
        assert col_map["email"] == "email"
        assert col_map["score"] == "float"
        assert col_map["active"] == "boolean"
        assert col_map["joined"] == "date"

    def test_enum_detected_from_repeated_values(self, tmp_path):
        rows = [{"status": s} for s in ["active", "inactive", "pending"] * 5]
        pf = _make_csv(rows, str(tmp_path), "records.csv")
        schema = infer_schema([pf])
        col = schema["tables"][0]["columns"][0]
        assert col["type"] == "enum"
        assert set(col["enum_values"]) == {"active", "inactive", "pending"}

    def test_sample_values_captured(self, tmp_path):
        rows = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]
        pf = _make_csv(rows, str(tmp_path), "people.csv")
        schema = infer_schema([pf])
        col = schema["tables"][0]["columns"][0]
        assert len(col["sample_values"]) > 0
        assert "Alice" in col["sample_values"]

    def test_file_with_no_context_text_returns_empty_relationships(self, tmp_path):
        rows = [{"id": 1, "title": "Thing"}]
        pf = _make_csv(rows, str(tmp_path), "items.csv")
        schema = infer_schema([pf])
        # Single table → no relationships
        assert schema["relationships"] == []


# ─── Requirement 2b: Text-only (no files) ────────────────────────────────────

class TestTextOnlyMode:

    def test_returns_schema_from_context_text(self):
        ctx = "Generate a dataset with columns: id, name, email, status, created_at"
        schema = infer_schema([], ctx)
        assert len(schema["tables"]) == 1
        col_names = [c["name"] for c in schema["tables"][0]["columns"]]
        assert "id" in col_names
        assert "email" in col_names
        assert "status" in col_names

    def test_table_name_extracted_from_context(self):
        ctx = "Table called orders with fields: id, customer_id, total, created_at"
        schema = infer_schema([], ctx)
        assert schema["tables"][0]["table_name"] == "orders"

    def test_type_hints_applied_from_column_names(self):
        ctx = "Table called ledger with fields: id, amount, created_at, is_active"
        schema = infer_schema([], ctx)
        col_map = {c["name"]: c["type"] for c in schema["tables"][0]["columns"]}
        assert col_map["id"] in ("integer", "string")   # id → integer hint
        assert col_map["amount"] == "float"
        assert col_map["created_at"] == "date"
        assert col_map["is_active"] == "boolean"

    def test_minimal_fallback_schema_when_no_fields_detected(self):
        ctx = "Just some dataset with random data please"
        schema = infer_schema([], ctx)
        assert len(schema["tables"]) == 1
        # Should produce at least a minimal column set
        assert len(schema["tables"][0]["columns"]) > 0

    def test_empty_string_context_with_no_files_still_returns_schema(self):
        # Both empty → should still return something (not crash)
        schema = infer_schema([], "")
        # Returns the context-based fallback (empty context → minimal schema)
        assert "tables" in schema


# ─── Requirement 1: BOTH file + context text ────────────────────────────────

class TestFileAndContextCombined:
    """
    When both a file and context text are supplied, the infer_schema call
    returns a file-derived schema. The context_text is used downstream
    (by compliance detection and context_extractor) but the base table
    structure comes from the file.
    """

    def test_file_columns_preserved_when_context_also_supplied(self, tmp_path):
        rows = [{"id": 1, "full_name": "Alice", "card_number": "4111111111111111"}]
        pf = _make_csv(rows, str(tmp_path), "customers.csv")
        # Context hints at PCI compliance — doesn't change column structure
        ctx = "PCI-compliant payment data for cardholders"
        schema = infer_schema([pf], ctx)
        col_names = [c["name"] for c in schema["tables"][0]["columns"]]
        assert "full_name" in col_names
        assert "card_number" in col_names

    def test_file_table_name_takes_precedence_over_context(self, tmp_path):
        rows = [{"id": 1, "amount": "100.00"}]
        pf = _make_csv(rows, str(tmp_path), "transactions.csv")
        ctx = "Table called ledger with financial data"
        schema = infer_schema([pf], ctx)
        # File-derived table name wins
        assert schema["tables"][0]["table_name"] == "transactions"

    def test_context_does_not_duplicate_tables(self, tmp_path):
        rows = [{"id": 1, "name": "Alice"}]
        pf = _make_csv(rows, str(tmp_path), "users.csv")
        ctx = "Users with personal data including name and email"
        schema = infer_schema([pf], ctx)
        assert len(schema["tables"]) == 1


# ─── Requirement 3: Multiple files → multi-table schema ──────────────────────

class TestMultipleFiles:

    def test_two_files_produce_two_tables(self, tmp_path):
        users_rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        orders_rows = [{"id": 1, "user_id": 1, "total": "9.99"}, {"id": 2, "user_id": 1, "total": "4.50"}]

        u_pf = _make_csv(users_rows, str(tmp_path), "users.csv")
        o_pf = _make_csv(orders_rows, str(tmp_path), "orders.csv")

        schema = infer_schema([u_pf, o_pf])
        table_names = [t["table_name"] for t in schema["tables"]]
        assert "users" in table_names
        assert "orders" in table_names

    def test_three_files_produce_three_tables(self, tmp_path):
        pfs = []
        for name in ("customers", "products", "invoices"):
            rows = [{"id": i, "name": f"{name}_{i}"} for i in range(1, 4)]
            pfs.append(_make_csv(rows, str(tmp_path), f"{name}.csv"))
        schema = infer_schema(pfs)
        assert len(schema["tables"]) == 3

    def test_fk_relationship_detected_across_files(self, tmp_path):
        users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        orders = [{"id": 1, "user_id": 1, "total": "5.00"}]
        u_pf = _make_csv(users, str(tmp_path), "users.csv")
        o_pf = _make_csv(orders, str(tmp_path), "orders.csv")
        schema = infer_schema([u_pf, o_pf])

        rels = schema["relationships"]
        assert len(rels) > 0, "Expected FK relationship between orders.user_id → users.id"
        rel = rels[0]
        # Convention: source_table = parent (PK owner), target_table = child (FK holder)
        assert rel["source_table"] == "users"
        assert rel["source_column"] == "id"
        assert rel["target_table"] == "orders"
        assert rel["target_column"] == "user_id"

    def test_three_table_chain_relationships(self, tmp_path):
        """users → orders → order_items — all three FKs detected."""
        users    = [{"id": 1}]
        orders   = [{"id": 1, "user_id": 1}]
        items    = [{"id": 1, "order_id": 1, "qty": 2}]

        u_pf = _make_csv(users,  str(tmp_path), "users.csv")
        o_pf = _make_csv(orders, str(tmp_path), "orders.csv")
        i_pf = _make_csv(items,  str(tmp_path), "order_items.csv")

        schema = infer_schema([u_pf, o_pf, i_pf])
        rels = schema["relationships"]
        # Convention: FK columns live in target_column (child table)
        tgt_cols = {r["target_column"] for r in rels}
        assert "user_id" in tgt_cols
        assert "order_id" in tgt_cols

    def test_no_spurious_self_relationships(self, tmp_path):
        """A table should never FK to itself."""
        rows = [{"id": 1, "parent_id": None}]
        pf = _make_csv(rows, str(tmp_path), "categories.csv")
        schema = infer_schema([pf])
        for r in schema["relationships"]:
            assert r["source_table"] != r["target_table"]

    def test_each_table_preserves_own_columns(self, tmp_path):
        users  = [{"id": 1, "email": "a@b.com"}]
        orders = [{"id": 1, "user_id": 1, "amount": "5.00"}]
        u_pf = _make_csv(users,  str(tmp_path), "users.csv")
        o_pf = _make_csv(orders, str(tmp_path), "orders.csv")
        schema = infer_schema([u_pf, o_pf])

        tmap = {t["table_name"]: t for t in schema["tables"]}
        u_cols = {c["name"] for c in tmap["users"]["columns"]}
        o_cols = {c["name"] for c in tmap["orders"]["columns"]}
        assert u_cols == {"id", "email"}
        assert o_cols == {"id", "user_id", "amount"}

    def test_multiple_files_with_context_text(self, tmp_path):
        users  = [{"id": 1, "email": "a@b.com"}]
        orders = [{"id": 1, "user_id": 1, "amount": "10.00"}]
        u_pf = _make_csv(users,  str(tmp_path), "users.csv")
        o_pf = _make_csv(orders, str(tmp_path), "orders.csv")
        ctx = "E-commerce dataset with PCI compliance for orders"
        schema = infer_schema([u_pf, o_pf], ctx)
        assert len(schema["tables"]) == 2


# ─── Multi-table text-only context (new feature) ─────────────────────────────

MULTI_TABLE_CTX = """\
E-commerce platform data for load testing our checkout pipeline.

We need 4 related datasets:

1. customers — id, first_name, last_name, email, phone, date_of_birth, loyalty_tier, is_active, created_at
2. addresses — id, customer_id, street, city, state, zip, country, is_default
3. orders — id, customer_id, status, total_amount, created_at, shipped_at
4. order_items — id, order_id, product_name, sku, quantity, unit_price, line_total

Distribution: 50% Gold, 30% Silver, 20% Bronze. 80% active.
Generate 200 rows per table.
"""


class TestMultiTableTextContext:

    def test_four_tables_detected_from_numbered_list(self):
        schema = infer_schema([], MULTI_TABLE_CTX)
        names = [t["table_name"] for t in schema["tables"]]
        assert set(names) == {"customers", "addresses", "orders", "order_items"}, (
            f"Expected 4 tables, got: {names}"
        )

    def test_each_table_has_correct_columns(self):
        schema = infer_schema([], MULTI_TABLE_CTX)
        tmap = {t["table_name"]: t for t in schema["tables"]}

        c_cols = {c["name"] for c in tmap["customers"]["columns"]}
        assert "email" in c_cols
        assert "loyalty_tier" in c_cols

        o_cols = {c["name"] for c in tmap["orders"]["columns"]}
        assert "customer_id" in o_cols
        assert "total_amount" in o_cols

        i_cols = {c["name"] for c in tmap["order_items"]["columns"]}
        assert "order_id" in i_cols
        assert "unit_price" in i_cols

    def test_fk_relationships_auto_detected(self):
        schema = infer_schema([], MULTI_TABLE_CTX)
        # Convention: source_table = parent (PK), target_table = child (FK holder)
        rels = {
            (r["source_table"], r["target_table"], r["target_column"])
            for r in schema["relationships"]
        }
        assert ("customers", "addresses",   "customer_id") in rels
        assert ("customers", "orders",      "customer_id") in rels
        assert ("orders",    "order_items", "order_id")    in rels

    def test_data_generates_for_all_four_tables(self):
        """Full round-trip: text → schema → generate_data → 4 tables with FK integrity."""
        import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from services.data_generator import generate_data

        schema = infer_schema([], MULTI_TABLE_CTX)
        rels   = schema["relationships"]
        data   = generate_data(schema, {}, {}, rels, volume=10,
                               llm_settings={"provider": "demo"})

        assert set(data.keys()) == {"customers", "addresses", "orders", "order_items"}

        # FK integrity
        customer_ids  = {r["id"]  for r in data["customers"]}
        order_ids     = {r["id"]  for r in data["orders"]}

        for row in data["addresses"]:
            assert row["customer_id"] in customer_ids
        for row in data["orders"]:
            assert row["customer_id"] in customer_ids
        for row in data["order_items"]:
            assert row["order_id"] in order_ids

    def test_numbered_list_with_colon_separator(self):
        ctx = """\
        1. users: id, name, email, created_at
        2. posts: id, user_id, title, body, published_at
        3. comments: id, post_id, user_id, content
        """
        schema = infer_schema([], ctx)
        names = [t["table_name"] for t in schema["tables"]]
        assert set(names) == {"users", "posts", "comments"}

    def test_relationships_detected_for_colon_separator_format(self):
        ctx = """\
        1. users: id, name, email
        2. posts: id, user_id, title
        3. comments: id, post_id, user_id, body
        """
        schema = infer_schema([], ctx)
        # Convention: FK column lives in target_table (child); check by (target_table, target_column)
        rels = {(r["target_table"], r["target_column"]) for r in schema["relationships"]}
        assert ("posts",    "user_id") in rels
        assert ("comments", "post_id") in rels
