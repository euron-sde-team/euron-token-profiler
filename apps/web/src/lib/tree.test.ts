import { describe, expect, it } from "vitest";

import { buildRows, timelineTicks } from "@/lib/tree";
import type { Span } from "@/lib/types";

function span(id: string, parent: string | null, start: number, end: number): Span {
  const at = (ms: number) => new Date(Date.UTC(2026, 10, 18, 10, 0, 0, ms)).toISOString();
  return {
    id,
    parent_id: parent,
    name: id,
    kind: "span",
    started_at: at(start),
    ended_at: at(end),
    duration_ms: end - start,
  } as Span;
}

describe("buildRows", () => {
  const spans = [
    span("c", "a", 600, 900),
    span("a", null, 0, 1000),
    span("b", "a", 100, 500),
    span("d", "b", 120, 200),
  ];

  it("orders depth first with children by start time", () => {
    const rows = buildRows(spans);
    expect(rows.map((r) => [r.span.id, r.depth])).toEqual([
      ["a", 0],
      ["b", 1],
      ["d", 2],
      ["c", 1],
    ]);
  });

  it("places spans on the trace timeline", () => {
    const [root, b] = buildRows(spans);
    expect(root).toMatchObject({ offset: 0, width: 1, descendants: 3 });
    expect(b?.offset).toBeCloseTo(0.1);
    expect(b?.width).toBeCloseTo(0.4);
  });

  it("hides the subtree of a collapsed span", () => {
    const rows = buildRows(spans, new Set(["b"]));
    expect(rows.map((r) => r.span.id)).toEqual(["a", "b", "c"]);
    expect(rows[1]?.collapsed).toBe(true);
  });

  it("keeps orphans visible as roots and survives cycles", () => {
    const orphan = [span("x", "missing", 0, 10), span("y", "z", 0, 10), span("z", "y", 5, 10)];
    expect(buildRows(orphan).map((r) => r.span.id)).toEqual(["x"]);
    expect(buildRows([span("only", "missing", 0, 0)])[0]?.width).toBeGreaterThan(0);
  });

  it("is empty for no spans", () => {
    expect(buildRows([])).toEqual([]);
  });
});

describe("timelineTicks", () => {
  it("labels quarters of the duration", () => {
    expect(timelineTicks(4000).map((t) => t.label)).toEqual(["0 ms", "1.0 s", "2.0 s", "3.0 s", "4.0 s"]);
    expect(timelineTicks(400)[2]).toEqual({ at: 0.5, label: "200 ms" });
  });
});
