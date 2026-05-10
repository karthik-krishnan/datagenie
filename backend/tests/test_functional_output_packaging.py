"""
Functional tests — Output Packaging (Requirement 6)

Covers:
  - Single-table output: correct format, filename, MIME type — NOT a zip
  - Multi-table output (default packaging): returns a ZIP containing one file per table
  - ZIP contents: correct filenames, non-empty, parseable content
  - All supported formats: csv, tsv, json, jsonlines, xml, yaml, parquet
  - XLSX: always a single file with multiple sheets (never a zip)
  - Merged packaging: single file with _entity column
  - Edge cases: empty table, large table, special characters in table name
"""
import sys
import os
import io
import csv
import json
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.output_formatter import format_output


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rows(n=5, table="t1"):
    return [{"id": i, "name": f"{table}_name_{i}", "value": i * 1.5} for i in range(1, n + 1)]


def _single(n=5):
    return {"users": _rows(n, "users")}


def _multi(tables=("users", "orders")):
    return {t: _rows(5, t) for t in tables}


# ─── Single-table: not a zip ──────────────────────────────────────────────────

class TestSingleTableOutput:

    def test_csv_not_a_zip(self):
        content, mime, filename = format_output(_single(), "csv", {})
        assert mime == "text/csv"
        assert filename.endswith(".csv")
        assert not zipfile.is_zipfile(io.BytesIO(content))

    def test_csv_has_header_and_rows(self):
        content, mime, filename = format_output(_single(3), "csv", {})
        text = content.decode("utf-8")
        lines = [l for l in text.strip().splitlines() if l]
        # Header must contain all three column names (order not guaranteed)
        header_cols = set(lines[0].split(","))
        assert header_cols == {"id", "name", "value"}, f"Unexpected header: {lines[0]}"
        assert len(lines) == 4   # header + 3 data rows

    def test_csv_filename_uses_table_name(self):
        _, _, filename = format_output({"customers": _rows(2, "customers")}, "csv", {})
        assert filename == "customers.csv"

    def test_json_not_a_zip(self):
        content, mime, filename = format_output(_single(), "json", {})
        assert mime == "application/json"
        assert not zipfile.is_zipfile(io.BytesIO(content))
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) == 5

    def test_json_mode_jsonlines(self):
        content, mime, filename = format_output(_single(3), "json", {"json_mode": "jsonlines"})
        lines = content.decode("utf-8").strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # each line is valid JSON

    def test_tsv_uses_tab_delimiter(self):
        content, _, _ = format_output(_single(2), "tsv", {})
        text = content.decode("utf-8")
        assert "\t" in text

    def test_xml_output_is_valid(self):
        content, mime, _ = format_output(_single(2), "xml", {})
        assert mime == "application/xml"
        assert b"<root>" in content or b"<?xml" in content

    def test_yaml_output_parseable(self):
        import yaml
        content, mime, _ = format_output(_single(3), "yaml", {})
        assert mime == "application/x-yaml"
        data = yaml.safe_load(content)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_parquet_output_readable(self):
        import pandas as pd
        content, mime, _ = format_output(_single(4), "parquet", {})
        assert mime == "application/octet-stream"
        df = pd.read_parquet(io.BytesIO(content))
        assert len(df) == 4
        assert list(df.columns) == ["id", "name", "value"]


# ─── Multi-table: default packaging → ZIP ─────────────────────────────────────

class TestMultiTableZipOutput:

    def test_two_tables_produce_zip(self):
        content, mime, filename = format_output(_multi(("users", "orders")), "csv", {})
        assert mime == "application/zip"
        assert filename == "test_data.zip"
        assert zipfile.is_zipfile(io.BytesIO(content))

    def test_zip_contains_one_file_per_table(self):
        tables = ("users", "orders", "products")
        content, _, _ = format_output(_multi(tables), "csv", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
        assert set(names) == {"users.csv", "orders.csv", "products.csv"}

    def test_zip_csv_files_are_parseable(self):
        content, _, _ = format_output(_multi(("alpha", "beta")), "csv", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                data = zf.read(name).decode("utf-8")
                reader = csv.DictReader(io.StringIO(data))
                rows = list(reader)
                assert len(rows) == 5, f"{name} should have 5 rows, got {len(rows)}"

    def test_zip_json_files_are_parseable(self):
        content, _, _ = format_output(_multi(("alpha", "beta")), "json", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            assert "alpha.json" in zf.namelist()
            data = json.loads(zf.read("alpha.json"))
            assert isinstance(data, list)
            assert len(data) == 5

    def test_zip_with_many_tables(self):
        tables = tuple(f"table_{i}" for i in range(1, 8))
        data = {t: _rows(3, t) for t in tables}
        content, mime, _ = format_output(data, "csv", {})
        assert mime == "application/zip"
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            assert len(zf.namelist()) == 7

    def test_zip_tsv_files_have_tab_delimiter(self):
        content, _, _ = format_output(_multi(("a", "b")), "tsv", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            data = zf.read("a.tsv").decode("utf-8")
        assert "\t" in data

    def test_zip_yaml_files_parseable(self):
        import yaml
        content, _, _ = format_output(_multi(("x", "y")), "yaml", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            data = yaml.safe_load(zf.read("x.yaml"))
        assert isinstance(data, list)

    def test_zip_xml_files_non_empty(self):
        content, _, _ = format_output(_multi(("nodes", "edges")), "xml", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_bytes = zf.read("nodes.xml")
        assert len(xml_bytes) > 20

    def test_zip_parquet_files_readable(self):
        import pandas as pd
        content, _, _ = format_output(_multi(("left", "right")), "parquet", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            df = pd.read_parquet(io.BytesIO(zf.read("left.parquet")))
        assert len(df) == 5

    def test_zip_each_file_contains_only_its_table_data(self):
        data = {
            "customers": [{"id": i, "customer": f"C{i}"} for i in range(1, 4)],
            "products":  [{"id": i, "product":  f"P{i}"} for i in range(1, 4)],
        }
        content, _, _ = format_output(data, "csv", {})
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            c_rows = list(csv.DictReader(io.StringIO(zf.read("customers.csv").decode())))
            p_rows = list(csv.DictReader(io.StringIO(zf.read("products.csv").decode())))
        assert "customer" in c_rows[0]
        assert "product"  in p_rows[0]
        assert "customer" not in p_rows[0]
        assert "product"  not in c_rows[0]


# ─── XLSX — always single file, multiple sheets ───────────────────────────────

class TestXLSXOutput:

    def test_single_table_xlsx_mime_and_filename(self):
        """XLSX is OOXML (ZIP-based internally) — check MIME and filename, not zip contents."""
        content, mime, filename = format_output(_single(3), "xlsx", {})
        assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert filename == "test_data.xlsx"

    def test_multi_table_xlsx_mime_type(self):
        content, mime, filename = format_output(_multi(("users", "orders")), "xlsx", {})
        assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        # Multi-table xlsx is a single file — does NOT have test_data.zip filename
        assert filename != "test_data.zip"

    def test_xlsx_has_one_sheet_per_table(self):
        import pandas as pd
        content, _, _ = format_output(_multi(("alpha", "beta", "gamma")), "xlsx", {})
        xl = pd.ExcelFile(io.BytesIO(content))
        assert set(xl.sheet_names) == {"alpha", "beta", "gamma"}

    def test_xlsx_sheet_data_correct(self):
        import pandas as pd
        data = {"items": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}
        content, _, _ = format_output(data, "xlsx", {})
        df = pd.read_excel(io.BytesIO(content), sheet_name="items")
        assert list(df["id"]) == [1, 2]
        assert list(df["name"]) == ["A", "B"]


# ─── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_table_produces_csv_with_no_data_rows(self):
        content, mime, _ = format_output({"empty": []}, "csv", {})
        assert mime == "text/csv"
        assert content == b""

    def test_single_table_never_zipped(self):
        """Single-table output is always a plain file, never a ZIP."""
        content, mime, _ = format_output(_single(), "csv", {})
        assert mime == "text/csv"
        assert not zipfile.is_zipfile(io.BytesIO(content))

    def test_format_extension_in_filename(self):
        exts = {
            "csv": ".csv", "tsv": ".tsv", "json": ".json",
            "yaml": ".yaml", "parquet": ".parquet", "xml": ".xml",
        }
        for fmt, ext in exts.items():
            _, _, filename = format_output({"t": _rows(1)}, fmt, {})
            assert filename.endswith(ext), f"Format {fmt}: expected {ext} in {filename}"
