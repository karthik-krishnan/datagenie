"""
Functional tests — Data Generation & Joins (Requirement 5)

Covers:
  - Single-table generation: volume, column coverage, type correctness
  - Relationship types: 1:many, many:many (via junction table), 1:1
  - FK referential integrity: child FK values are always valid parent PKs
  - Multi-hop chains (A→B→C): correct topological ordering
  - Topological sort correctness: parents always generated before children
  - Distributions (enum weights, boolean ratios)
  - Temporal aging for date columns
  - Circular-reference graceful degradation

Supported relationship types (documented constraints):
  - many_to_one / one_to_many: Fully enforced ✅
  - one_to_one: Enforced while parent pool not exhausted; extra rows fall back
                to many_to_one (volume must not exceed parent count for strict 1:1)
  - many_to_many: Supported via explicit junction table (FK pair uniqueness
                  not enforced — caller adds UNIQUE constraint in real DB if needed)
  - Circular references: NOT supported; isolated/circular tables appended in
                         undefined order after the DAG is resolved
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.data_generator import generate_data

DEMO_SETTINGS = {"provider": "demo", "api_key": "", "model": ""}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_schema(*tables):
    """Build a minimal schema dict from table specs.

    Each table spec is (name, [col_dicts]).  Each col_dict needs at minimum
    {"name": ..., "type": ...}.  'pii' key is optional.
    """
    return {
        "tables": [
            {"table_name": name, "filename": f"{name}.csv", "columns": cols, "row_count": 5}
            for name, cols in tables
        ],
        "relationships": [],
    }


def _col(name, type_="string", **kw):
    return {"name": name, "type": type_, "pattern": "generic", "sample_values": [], "enum_values": [], **kw}


# ─── Basic single-table generation ────────────────────────────────────────────

class TestSingleTableGeneration:

    def test_correct_volume(self):
        schema = _make_schema(("users", [_col("id", "integer"), _col("name")]))
        data = generate_data(schema, {}, {}, [], volume=25, llm_settings=DEMO_SETTINGS)
        assert len(data["users"]) == 25

    def test_all_columns_present_in_every_row(self):
        schema = _make_schema(("users", [
            _col("id", "integer"), _col("name"), _col("email", "email"),
            _col("active", "boolean"), _col("score", "float"),
        ]))
        data = generate_data(schema, {}, {}, [], volume=10, llm_settings=DEMO_SETTINGS)
        for row in data["users"]:
            assert set(row.keys()) == {"id", "name", "email", "active", "score"}

    def test_integer_id_auto_increments(self):
        schema = _make_schema(("items", [_col("id", "integer"), _col("name")]))
        data = generate_data(schema, {}, {}, [], volume=5, llm_settings=DEMO_SETTINGS)
        ids = [row["id"] for row in data["items"]]
        assert ids == list(range(1, 6)), f"Expected [1..5], got {ids}"

    def test_boolean_column_values(self):
        schema = _make_schema(("flags", [_col("id", "integer"), _col("active", "boolean")]))
        data = generate_data(schema, {}, {}, [], volume=20, llm_settings=DEMO_SETTINGS)
        vals = {row["active"] for row in data["flags"]}
        assert vals <= {True, False}

    def test_email_column_contains_at(self):
        schema = _make_schema(("users", [_col("id", "integer"), _col("email", "email")]))
        data = generate_data(schema, {}, {}, [], volume=10, llm_settings=DEMO_SETTINGS)
        for row in data["users"]:
            assert "@" in str(row["email"])

    def test_enum_column_stays_within_enum_values(self):
        schema = _make_schema(("orders", [
            _col("id", "integer"),
            _col("status", "enum", enum_values=["pending", "shipped", "delivered"]),
        ]))
        data = generate_data(schema, {}, {}, [], volume=20, llm_settings=DEMO_SETTINGS)
        valid = {"pending", "shipped", "delivered"}
        for row in data["orders"]:
            assert row["status"] in valid, f"Unexpected status: {row['status']}"

    def test_preview_mode_generates_five_rows(self):
        """The router caps volume to 5 for preview; the service uses whatever volume is passed."""
        schema = _make_schema(("users", [_col("id", "integer"), _col("name")]))
        data = generate_data(schema, {}, {}, [], volume=5, llm_settings=DEMO_SETTINGS, preview=True)
        assert len(data["users"]) == 5


# ─── Enum & boolean distributions ─────────────────────────────────────────────

class TestDistributions:

    def test_enum_distribution_respected(self):
        """80% active / 20% inactive should be roughly honoured over 1000 rows."""
        schema = _make_schema(("users", [
            _col("id", "integer"),
            _col("status", "enum", enum_values=["active", "inactive"]),
        ]))
        distributions = {"status": {"active": 80, "inactive": 20}}
        data = generate_data(schema, {"distributions": distributions}, {}, [], volume=1000, llm_settings=DEMO_SETTINGS)
        statuses = [r["status"] for r in data["users"]]
        active_pct = statuses.count("active") / len(statuses)
        assert 0.70 <= active_pct <= 0.90, f"active% = {active_pct:.2%} — too far from 80%"

    def test_boolean_distribution_respected(self):
        schema = _make_schema(("users", [_col("id", "integer"), _col("subscribed", "boolean")]))
        distributions = {"subscribed": {"true_ratio": 0.7}}
        data = generate_data(schema, {"distributions": distributions}, {}, [], volume=1000, llm_settings=DEMO_SETTINGS)
        vals = [r["subscribed"] for r in data["users"]]
        true_pct = vals.count(True) / len(vals)
        assert 0.60 <= true_pct <= 0.80, f"true% = {true_pct:.2%} — too far from 70%"

    def test_three_way_enum_distribution(self):
        schema = _make_schema(("payments", [
            _col("id", "integer"),
            _col("method", "enum", enum_values=["card", "cash", "crypto"]),
        ]))
        distributions = {"method": {"card": 60, "cash": 30, "crypto": 10}}
        data = generate_data(schema, {"distributions": distributions}, {}, [], volume=1000, llm_settings=DEMO_SETTINGS)
        from collections import Counter
        counts = Counter(r["method"] for r in data["payments"])
        assert counts["card"] > counts["cash"] > counts["crypto"], (
            "Distribution order not preserved"
        )


# ─── Temporal aging ──────────────────────────────────────────────────────────

class TestTemporalAging:

    def test_date_column_aged_within_window(self):
        from datetime import date, timedelta
        schema = _make_schema(("events", [_col("id", "integer"), _col("event_date", "date")]))
        temporal = {"event_date": {"days_back": 90}}
        data = generate_data(schema, {"temporal": temporal}, {}, [], volume=20, llm_settings=DEMO_SETTINGS)
        today = date.today()
        for row in data["events"]:
            d = date.fromisoformat(str(row["event_date"]))
            assert (today - timedelta(days=91)) <= d <= today, (
                f"event_date {d} outside 90-day window"
            )


# ─── Joins: Requirement 5 ─────────────────────────────────────────────────────

class TestOneToManyJoin:
    """One parent can have many children (users → orders)."""

    def _schema_users_orders(self):
        return _make_schema(
            ("users",  [_col("id", "integer"), _col("name")]),
            ("orders", [_col("id", "integer"), _col("user_id", "integer"), _col("total", "float")]),
        )

    def _rels(self):
        return [{
            "source_table": "orders", "source_column": "user_id",
            "target_table": "users",  "target_column": "id",
            "cardinality":  "many_to_one", "confidence": 0.9,
        }]

    def test_all_order_user_ids_reference_valid_users(self):
        schema = self._schema_users_orders()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        user_ids = {r["id"] for r in data["users"]}
        for order in data["orders"]:
            assert order["user_id"] in user_ids, (
                f"orders.user_id={order['user_id']} not in users.id set {user_ids}"
            )

    def test_multiple_orders_per_user_allowed(self):
        schema = self._schema_users_orders()
        data = generate_data(schema, {}, {}, self._rels(), volume=5, llm_settings=DEMO_SETTINGS)
        # With 5 users and 5 orders, some users may share — that's valid for 1:many
        user_ids_used = [r["user_id"] for r in data["orders"]]
        # At least the value set is valid
        valid = {r["id"] for r in data["users"]}
        assert all(uid in valid for uid in user_ids_used)

    def test_fk_integrity_with_large_volume(self):
        schema = self._schema_users_orders()
        data = generate_data(schema, {}, {}, self._rels(), volume=50, llm_settings=DEMO_SETTINGS)
        user_ids = {r["id"] for r in data["users"]}
        for order in data["orders"]:
            assert order["user_id"] in user_ids


class TestOneToOneJoin:
    """Each parent row matched to at most one child row."""

    def _schema(self):
        return _make_schema(
            ("users",    [_col("id", "integer"), _col("name")]),
            ("profiles", [_col("id", "integer"), _col("user_id", "integer"), _col("bio")]),
        )

    def _rels(self):
        return [{
            "source_table": "profiles", "source_column": "user_id",
            "target_table": "users",    "target_column": "id",
            "cardinality":  "one_to_one", "confidence": 0.9,
        }]

    def test_all_profile_user_ids_reference_valid_users(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=5, llm_settings=DEMO_SETTINGS)
        user_ids = {r["id"] for r in data["users"]}
        for profile in data["profiles"]:
            assert profile["user_id"] in user_ids

    def test_each_user_referenced_at_most_once(self):
        """1:1 — no user_id should appear more than once in profiles."""
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=5, llm_settings=DEMO_SETTINGS)
        user_ids_used = [r["user_id"] for r in data["profiles"]]
        assert len(user_ids_used) == len(set(user_ids_used)), (
            f"Duplicate user_ids in profiles for 1:1 join: {user_ids_used}"
        )

    def test_volume_equals_parent_count_for_strict_one_to_one(self):
        """When volume == parent count, every parent gets exactly one child."""
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=8, llm_settings=DEMO_SETTINGS)
        user_ids_used = [r["user_id"] for r in data["profiles"]]
        user_ids_all  = [r["id"]      for r in data["users"]]
        assert sorted(user_ids_used) == sorted(user_ids_all), (
            "Every user should have exactly one profile when volume matches"
        )


class TestManyToManyJoin:
    """Many-to-many via a junction table (students ↔ courses via enrollments)."""

    def _schema(self):
        return _make_schema(
            ("students",    [_col("id", "integer"), _col("name")]),
            ("courses",     [_col("id", "integer"), _col("title")]),
            ("enrollments", [
                _col("id", "integer"),
                _col("student_id", "integer"),
                _col("course_id",  "integer"),
            ]),
        )

    def _rels(self):
        return [
            {
                "source_table": "enrollments", "source_column": "student_id",
                "target_table": "students",    "target_column": "id",
                "cardinality":  "many_to_one",  "confidence": 0.9,
            },
            {
                "source_table": "enrollments", "source_column": "course_id",
                "target_table": "courses",     "target_column": "id",
                "cardinality":  "many_to_one",  "confidence": 0.9,
            },
        ]

    def test_all_enrollment_student_ids_valid(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        student_ids = {r["id"] for r in data["students"]}
        for enroll in data["enrollments"]:
            assert enroll["student_id"] in student_ids

    def test_all_enrollment_course_ids_valid(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        course_ids = {r["id"] for r in data["courses"]}
        for enroll in data["enrollments"]:
            assert enroll["course_id"] in course_ids

    def test_junction_table_has_correct_volume(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=15, llm_settings=DEMO_SETTINGS)
        assert len(data["enrollments"]) == 15

    def test_all_three_tables_present(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        assert set(data.keys()) == {"students", "courses", "enrollments"}


class TestMultiHopChainJoin:
    """Three-table chain: users → orders → order_items (A→B→C)."""

    def _schema(self):
        return _make_schema(
            ("users",       [_col("id", "integer"), _col("name")]),
            ("orders",      [_col("id", "integer"), _col("user_id", "integer"), _col("total", "float")]),
            ("order_items", [_col("id", "integer"), _col("order_id", "integer"), _col("qty", "integer")]),
        )

    def _rels(self):
        return [
            {
                "source_table": "orders",      "source_column": "user_id",
                "target_table": "users",        "target_column": "id",
                "cardinality":  "many_to_one",  "confidence": 0.9,
            },
            {
                "source_table": "order_items",  "source_column": "order_id",
                "target_table": "orders",        "target_column": "id",
                "cardinality":  "many_to_one",  "confidence": 0.9,
            },
        ]

    def test_order_items_reference_valid_order_ids(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        order_ids = {r["id"] for r in data["orders"]}
        for item in data["order_items"]:
            assert item["order_id"] in order_ids, (
                f"order_items.order_id={item['order_id']} not in orders.id {order_ids}"
            )

    def test_orders_reference_valid_user_ids(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        user_ids = {r["id"] for r in data["users"]}
        for order in data["orders"]:
            assert order["user_id"] in user_ids

    def test_topological_order_observed(self):
        """Verify all three tables generated in the correct dependency order."""
        schema = self._schema()
        # We just assert no KeyError / assertion error (topology is internal)
        data = generate_data(schema, {}, {}, self._rels(), volume=10, llm_settings=DEMO_SETTINGS)
        assert "users" in data and "orders" in data and "order_items" in data

    def test_all_tables_have_correct_volume(self):
        schema = self._schema()
        data = generate_data(schema, {}, {}, self._rels(), volume=8, llm_settings=DEMO_SETTINGS)
        assert len(data["users"])       == 8
        assert len(data["orders"])      == 8
        assert len(data["order_items"]) == 8


class TestJoinEdgeCases:

    def test_no_relationships_generates_independent_tables(self):
        schema = _make_schema(
            ("alpha", [_col("id", "integer"), _col("val")]),
            ("beta",  [_col("id", "integer"), _col("val")]),
        )
        data = generate_data(schema, {}, {}, [], volume=5, llm_settings=DEMO_SETTINGS)
        assert set(data.keys()) == {"alpha", "beta"}
        assert len(data["alpha"]) == 5
        assert len(data["beta"])  == 5

    def test_self_referential_table_does_not_crash(self):
        """A table with a parent_id pointing to itself should not infinite-loop."""
        schema = _make_schema(
            ("categories", [_col("id", "integer"), _col("parent_id", "integer"), _col("name")]),
        )
        # No relationship registered — self-ref is just a regular column
        data = generate_data(schema, {}, {}, [], volume=5, llm_settings=DEMO_SETTINGS)
        assert len(data["categories"]) == 5

    def test_circular_relationship_does_not_crash(self):
        """A↔B circular FK — tables may generate in undefined order but must not crash."""
        schema = _make_schema(
            ("a", [_col("id", "integer"), _col("b_id", "integer")]),
            ("b", [_col("id", "integer"), _col("a_id", "integer")]),
        )
        rels = [
            {"source_table": "a", "source_column": "b_id",
             "target_table": "b", "target_column": "id",
             "cardinality": "many_to_one", "confidence": 0.9},
            {"source_table": "b", "source_column": "a_id",
             "target_table": "a", "target_column": "id",
             "cardinality": "many_to_one", "confidence": 0.9},
        ]
        # Should not raise — one direction will miss FKs but generation completes
        data = generate_data(schema, {}, {}, rels, volume=5, llm_settings=DEMO_SETTINGS)
        assert "a" in data and "b" in data
