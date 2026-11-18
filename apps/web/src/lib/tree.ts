import type { Span } from "@/lib/types";

export type TreeRow = {
  span: Span;
  depth: number;
  /** Where the span starts, as a fraction of the whole trace (0 to 1). */
  offset: number;
  /** How much of the trace it covers (0 to 1, never below a visible sliver). */
  width: number;
  /** Spans below this one, counting all depths. */
  descendants: number;
  /** The span has children that are hidden because it is collapsed. */
  collapsed: boolean;
};

const MIN_WIDTH = 0.004;

/**
 * Order spans as a depth-first tree (children by start time) and place each on the trace's
 * timeline. A span whose parent is missing (sampled out, still in flight, or sent from
 * another process) becomes a root instead of vanishing. Collapsed spans hide their subtree.
 */
export function buildRows(spans: Span[], collapsed: ReadonlySet<string> = new Set()): TreeRow[] {
  if (spans.length === 0) return [];
  const ids = new Set(spans.map((s) => s.id));
  const children = new Map<string | null, Span[]>();
  for (const span of spans) {
    const parent = span.parent_id && ids.has(span.parent_id) ? span.parent_id : null;
    const list = children.get(parent) ?? [];
    list.push(span);
    children.set(parent, list);
  }
  const byStart = (a: Span, b: Span) =>
    new Date(a.started_at).getTime() - new Date(b.started_at).getTime() || a.id.localeCompare(b.id);
  for (const list of children.values()) list.sort(byStart);

  const start = Math.min(...spans.map((s) => new Date(s.started_at).getTime()));
  const end = Math.max(...spans.map((s) => new Date(s.ended_at).getTime()));
  const total = Math.max(1, end - start);

  const count = (id: string): number => (children.get(id) ?? []).reduce((sum, c) => sum + 1 + count(c.id), 0);
  const rows: TreeRow[] = [];
  const visit = (span: Span, depth: number, seen: Set<string>) => {
    if (seen.has(span.id)) return;
    seen.add(span.id);
    const from = new Date(span.started_at).getTime() - start;
    const length = new Date(span.ended_at).getTime() - new Date(span.started_at).getTime();
    const hidden = collapsed.has(span.id);
    rows.push({
      span,
      depth,
      offset: from / total,
      width: Math.min(1 - from / total, Math.max(MIN_WIDTH, length / total)),
      descendants: count(span.id),
      collapsed: hidden,
    });
    if (hidden) return;
    for (const child of children.get(span.id) ?? []) visit(child, depth + 1, seen);
  };
  for (const root of children.get(null) ?? []) visit(root, 0, new Set());
  return rows;
}

/** Tick labels for the waterfall header: 0, 25, 50, 75 and 100 percent of the duration. */
export function timelineTicks(durationMs: number): { at: number; label: string }[] {
  return [0, 0.25, 0.5, 0.75, 1].map((at) => {
    const ms = durationMs * at;
    return { at, label: ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s` };
  });
}

/** Share of the timeline a "8.8 s - $0.013" label can take; sized for a phone-width track. */
const LABEL_SHARE = 0.3;

export type LabelPlacement = "after" | "before" | "inside";

/**
 * Where a bar's duration and cost label goes. Prefer the free space after the bar, then the
 * free space before it. A bar that spans most of the track leaves neither, so the label sits on
 * the bar itself: putting it before the bar would push it left across the span-name column.
 */
export function labelPlacement(offset: number, width: number): LabelPlacement {
  if (offset + width + LABEL_SHARE <= 1) return "after";
  if (offset >= LABEL_SHARE) return "before";
  return "inside";
}
