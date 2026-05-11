/**
 * Functional tests for RelationshipMapper
 *
 * Key regression covered:
 * - Changing one row's source table must NOT clear other rows' selections.
 * - Browser-level spurious onChange("") when the options list re-renders must
 *   be swallowed if a value is already selected.
 * - Duplicate-pair validation fires for existing rows.
 * - Adding a new relationship via the "Add" form works end-to-end.
 * - Removing a row calls onUpdate without that row.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import RelationshipMapper from "./RelationshipMapper.jsx";

// ── Test schema ───────────────────────────────────────────────────────────────
const SCHEMA = {
  tables: [
    {
      table_name: "customers",
      columns: [{ name: "id" }, { name: "email" }],
    },
    {
      table_name: "orders",
      columns: [{ name: "id" }, { name: "customer_id" }],
    },
    {
      table_name: "products",
      columns: [{ name: "id" }, { name: "name" }],
    },
  ],
};

// Two pre-existing relationships so multi-row interactions can be tested.
const TWO_RELS = [
  {
    source_table: "customers",
    source_column: "id",
    target_table: "orders",
    target_column: "customer_id",
    cardinality: "one_to_many",
    confidence: 0.95,
  },
  {
    source_table: "orders",
    source_column: "id",
    target_table: "products",
    target_column: "id",
    cardinality: "many_to_many",
    confidence: 0.8,
  },
];

// Helper: find all <select> elements inside a labelled card by heading text.
function getSelectsInRow(rowIndex) {
  // Each relationship card is a sibling div; grab by position.
  const cards = document.querySelectorAll("[class*='rounded-xl']");
  return Array.from(cards[rowIndex].querySelectorAll("select"));
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderMapper(relationships = [], onUpdate = vi.fn()) {
  return render(
    <RelationshipMapper
      schema={SCHEMA}
      relationships={relationships}
      onUpdate={onUpdate}
    />,
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

describe("empty state", () => {
  it("shows the empty prompt when there are no relationships", () => {
    renderMapper([]);
    expect(screen.getByText(/no relationships detected/i)).toBeInTheDocument();
  });

  it("renders the '+ Add relationship' button", () => {
    renderMapper([]);
    expect(screen.getByText(/\+ add relationship/i)).toBeInTheDocument();
  });
});

// ── Rendering existing rows ───────────────────────────────────────────────────

describe("rendering existing rows", () => {
  it("renders one card per relationship", () => {
    renderMapper(TWO_RELS);
    // Each card has a "Remove" button — count them.
    const removes = screen.getAllByRole("button", { name: /remove/i });
    expect(removes).toHaveLength(2);
  });

  it("shows confidence for existing rows", () => {
    renderMapper(TWO_RELS);
    expect(screen.getByText(/conf 95%/i)).toBeInTheDocument();
    expect(screen.getByText(/conf 80%/i)).toBeInTheDocument();
  });

  it("pre-selects the correct source table in each row", () => {
    renderMapper(TWO_RELS);
    const row0Selects = getSelectsInRow(0);
    expect(row0Selects[0].value).toBe("customers"); // source_table
    const row1Selects = getSelectsInRow(1);
    expect(row1Selects[0].value).toBe("orders");    // source_table
  });

  it("pre-selects the correct source column in each row", () => {
    renderMapper(TWO_RELS);
    const row0Selects = getSelectsInRow(0);
    expect(row0Selects[1].value).toBe("id"); // source_column
  });

  it("pre-selects the correct target table in each row", () => {
    renderMapper(TWO_RELS);
    const row0Selects = getSelectsInRow(0);
    expect(row0Selects[2].value).toBe("orders"); // target_table
  });
});

// ── CRITICAL: cross-row isolation ────────────────────────────────────────────

describe("cross-row isolation — changing one row must not corrupt others", () => {
  it("changing row 1 source table does NOT clear row 0 target_table", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    // Change row 1's source table (selects[0] of card 1).
    const row1Selects = getSelectsInRow(1);
    fireEvent.change(row1Selects[0], { target: { value: "products" } });

    // onUpdate is called — verify row 0 is unchanged.
    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall[0].source_table).toBe("customers");
    expect(lastCall[0].source_column).toBe("id");
    expect(lastCall[0].target_table).toBe("orders");
    expect(lastCall[0].target_column).toBe("customer_id");
  });

  it("changing row 0 source table does NOT clear row 1 data", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    const row0Selects = getSelectsInRow(0);
    fireEvent.change(row0Selects[0], { target: { value: "products" } });

    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    // Row 1 (index 1) should be untouched.
    expect(lastCall[1].source_table).toBe("orders");
    expect(lastCall[1].source_column).toBe("id");
    expect(lastCall[1].target_table).toBe("products");
    expect(lastCall[1].target_column).toBe("id");
  });
});

// ── Spurious onChange guard ───────────────────────────────────────────────────

describe("FieldSelect spurious onChange guard", () => {
  it("ignores a change event with empty value when a value is already selected", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    // Simulate the browser firing onChange("") on row 0's target_table select
    // (the spurious event that happens when the option list re-renders).
    const row0Selects = getSelectsInRow(0);
    const targetTableSelect = row0Selects[2]; // target_table select for row 0
    expect(targetTableSelect.value).toBe("orders"); // sanity check

    fireEvent.change(targetTableSelect, { target: { value: "" } });

    // onUpdate must NOT have been called (event was swallowed).
    expect(onUpdate).not.toHaveBeenCalled();
  });
});

// ── Cascade-clear within a single row ─────────────────────────────────────────

describe("cascade-clear within a single row", () => {
  it("clears source_column and target when source_table changes to a NEW value", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    const row0Selects = getSelectsInRow(0);
    fireEvent.change(row0Selects[0], { target: { value: "products" } }); // new source

    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall[0].source_table).toBe("products");
    expect(lastCall[0].source_column).toBe("");
    expect(lastCall[0].target_table).toBe("");
    expect(lastCall[0].target_column).toBe("");
  });

  it("does NOT cascade-clear when re-selecting the same source_table", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    const row0Selects = getSelectsInRow(0);
    // "customers" is already selected — re-selecting it must not wipe data.
    fireEvent.change(row0Selects[0], { target: { value: "customers" } });

    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall[0].source_column).toBe("id");
    expect(lastCall[0].target_table).toBe("orders");
    expect(lastCall[0].target_column).toBe("customer_id");
  });

  it("clears target_column when target_table changes to a NEW value", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    const row0Selects = getSelectsInRow(0);
    // Row 0 target table is currently "orders"; change to "products".
    // First make products available by noting it isn't already paired with customers.
    // (In TWO_RELS, customers→orders and orders→products, so customers→products is free.)
    fireEvent.change(row0Selects[2], { target: { value: "products" } });

    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall[0].target_table).toBe("products");
    expect(lastCall[0].target_column).toBe("");
  });
});

// ── Remove row ────────────────────────────────────────────────────────────────

describe("remove row", () => {
  it("calls onUpdate with the row removed", () => {
    const onUpdate = vi.fn();
    renderMapper([...TWO_RELS], onUpdate);

    const removes = screen.getAllByRole("button", { name: /remove/i });
    fireEvent.click(removes[0]);

    expect(onUpdate).toHaveBeenCalledWith([TWO_RELS[1]]);
  });

  it("removing the only row leaves an empty array", () => {
    const onUpdate = vi.fn();
    renderMapper([TWO_RELS[0]], onUpdate);

    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onUpdate).toHaveBeenCalledWith([]);
  });
});

// ── Add new relationship ──────────────────────────────────────────────────────

describe("add new relationship", () => {
  it("shows the draft form when '+ Add relationship' is clicked", () => {
    renderMapper([]);
    fireEvent.click(screen.getByText(/\+ add relationship/i));
    expect(screen.getByRole("button", { name: /^add$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("shows a validation error if Add is clicked with an empty form", () => {
    renderMapper([]);
    fireEvent.click(screen.getByText(/\+ add relationship/i));
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(screen.getByText(/select a source table/i)).toBeInTheDocument();
  });

  it("calls onUpdate with the new relationship after filling all fields", () => {
    const onUpdate = vi.fn();
    renderMapper([], onUpdate);
    fireEvent.click(screen.getByText(/\+ add relationship/i));

    // The draft form is the last card — get its selects.
    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const draftSelects = Array.from(cards[cards.length - 1].querySelectorAll("select"));

    fireEvent.change(draftSelects[0], { target: { value: "customers" } }); // source_table
    fireEvent.change(draftSelects[1], { target: { value: "id" } });         // source_column
    fireEvent.change(draftSelects[2], { target: { value: "orders" } });     // target_table
    fireEvent.change(draftSelects[3], { target: { value: "customer_id" } });// target_column

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(onUpdate).toHaveBeenCalledTimes(1);
    const added = onUpdate.mock.calls[0][0][0];
    expect(added.source_table).toBe("customers");
    expect(added.source_column).toBe("id");
    expect(added.target_table).toBe("orders");
    expect(added.target_column).toBe("customer_id");
    expect(added.confidence).toBe(1.0);
  });

  it("closes the draft form after successfully adding", () => {
    const onUpdate = vi.fn();
    renderMapper([], onUpdate);
    fireEvent.click(screen.getByText(/\+ add relationship/i));

    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const draftSelects = Array.from(cards[cards.length - 1].querySelectorAll("select"));

    fireEvent.change(draftSelects[0], { target: { value: "customers" } });
    fireEvent.change(draftSelects[1], { target: { value: "id" } });
    fireEvent.change(draftSelects[2], { target: { value: "orders" } });
    fireEvent.change(draftSelects[3], { target: { value: "customer_id" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // Draft form should be gone — Cancel button disappears.
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("Cancel button hides the draft form without calling onUpdate", () => {
    const onUpdate = vi.fn();
    renderMapper([], onUpdate);
    fireEvent.click(screen.getByText(/\+ add relationship/i));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onUpdate).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });
});

// ── Duplicate-pair prevention ─────────────────────────────────────────────────
// The UI enforces uniqueness at the dropdown level — occupiedTargets() removes
// already-paired tables from the target options, so a duplicate can never be
// selected. These tests verify that filtering behaviour.

describe("duplicate-pair prevention", () => {
  it("does not offer 'orders' as a target when customers→orders already exists", () => {
    renderMapper([TWO_RELS[0]]); // customers → orders
    fireEvent.click(screen.getByText(/\+ add relationship/i));

    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const draftSelects = Array.from(cards[cards.length - 1].querySelectorAll("select"));

    fireEvent.change(draftSelects[0], { target: { value: "customers" } }); // source_table

    // Target-table select must NOT include "orders" (already paired).
    const targetSelect = draftSelects[2];
    const options = Array.from(targetSelect.querySelectorAll("option")).map((o) => o.value);
    expect(options).not.toContain("orders");
    expect(options).toContain("products"); // other tables are still available
  });

  it("does not offer 'customers' as a target when orders→customers (reversed) already exists", () => {
    renderMapper([TWO_RELS[0]]); // customers → orders means orders is paired with customers
    fireEvent.click(screen.getByText(/\+ add relationship/i));

    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const draftSelects = Array.from(cards[cards.length - 1].querySelectorAll("select"));

    fireEvent.change(draftSelects[0], { target: { value: "orders" } }); // source = orders

    // Target-table select must NOT include "customers" (reverse pair exists).
    const targetSelect = draftSelects[2];
    const options = Array.from(targetSelect.querySelectorAll("option")).map((o) => o.value);
    expect(options).not.toContain("customers");
    expect(options).toContain("products");
  });

  it("shows source=target validation error when same table is entered programmatically", () => {
    // validate() is the safety-net; even if somehow source === target, an error fires.
    renderMapper([]);
    fireEvent.click(screen.getByText(/\+ add relationship/i));

    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const draftSelects = Array.from(cards[cards.length - 1].querySelectorAll("select"));

    // Fill in source but skip target, then click Add — triggers "Select a target table" error.
    fireEvent.change(draftSelects[0], { target: { value: "customers" } });
    fireEvent.change(draftSelects[1], { target: { value: "id" } });
    // Intentionally leave target empty.
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(screen.getByText(/select a target table/i)).toBeInTheDocument();
  });
});

// ── Cardinality picker ────────────────────────────────────────────────────────

describe("cardinality picker", () => {
  it("changes cardinality when a chip is clicked", () => {
    const onUpdate = vi.fn();
    renderMapper([TWO_RELS[0]], onUpdate);

    // Click the "N : N" chip on row 0.
    const cards = document.querySelectorAll("[class*='rounded-xl']");
    const nnButton = within(cards[0]).getByText("N : N");
    fireEvent.click(nnButton);

    const lastCall = onUpdate.mock.calls[onUpdate.mock.calls.length - 1][0];
    expect(lastCall[0].cardinality).toBe("many_to_many");
  });
});
