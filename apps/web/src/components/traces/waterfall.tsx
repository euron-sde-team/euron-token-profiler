"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { formatDuration, formatUsd } from "@/lib/format";
import { SPAN_COLOR, SPAN_KIND } from "@/lib/labels";
import { buildRows, timelineTicks } from "@/lib/tree";
import type { Span } from "@/lib/types";

/**
 * The span tree beside a timeline: each row is a span, indented by depth, with a bar placed
 * on the trace's own time axis. Rows are buttons: pick one to open it. A parent can be
 * collapsed to hide its subtree.
 */
export function Waterfall({
  spans,
  durationMs,
  selected,
  onSelect,
}: {
  spans: Span[];
  durationMs: number;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const rows = useMemo(() => buildRows(spans, collapsed), [spans, collapsed]);
  const ticks = timelineTicks(durationMs);

  function toggle(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="border-border bg-card overflow-hidden rounded-xl border shadow-sm">
      <div className="border-border bg-muted/60 grid grid-cols-[minmax(11rem,2fr)_3fr] border-b text-[11.5px]">
        <div className="text-muted-foreground px-3 py-2 font-medium">Span</div>
        <div className="relative h-8">
          {ticks.map((tick) => (
            <span
              key={tick.at}
              className="text-subtle tabular absolute top-2 -translate-x-1/2 whitespace-nowrap first:translate-x-0 last:-translate-x-full"
              style={{ left: `${tick.at * 100}%` }}
            >
              {tick.label}
            </span>
          ))}
        </div>
      </div>
      <ul aria-label="Spans">
        {rows.map((row) => {
          const { span } = row;
          const active = selected === span.id;
          const failed = span.status === "error";
          const hasChildren = row.descendants > 0;
          return (
            <li key={span.id} className="border-border border-b last:border-b-0">
              <div
                className={cn(
                  "grid grid-cols-[minmax(11rem,2fr)_3fr] items-center",
                  active ? "bg-accent/60" : "hover:bg-muted/50",
                )}
              >
                <div
                  className="flex min-w-0 items-center gap-1 py-1.5 pr-2 pl-1"
                  style={{ paddingLeft: 4 + row.depth * 16 }}
                >
                  {hasChildren ? (
                    <button
                      type="button"
                      aria-label={`${row.collapsed ? "Expand" : "Collapse"} ${span.name}`}
                      aria-expanded={!row.collapsed}
                      onClick={() => toggle(span.id)}
                      className="text-muted-foreground hover:text-foreground flex size-5 shrink-0 items-center justify-center rounded"
                    >
                      {row.collapsed ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                    </button>
                  ) : (
                    <span className="size-5 shrink-0" aria-hidden />
                  )}
                  <button
                    type="button"
                    onClick={() => onSelect(span.id)}
                    aria-current={active ? "true" : undefined}
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  >
                    <span
                      className="size-2.5 shrink-0 rounded-sm"
                      style={{ background: SPAN_COLOR[span.kind] }}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span className={cn("block truncate text-[13px] font-medium", failed && "text-danger")}>
                        {span.name}
                      </span>
                      <span className="text-muted-foreground block truncate text-[11.5px]">
                        {SPAN_KIND[span.kind].label}
                        {span.model ? ` - ${span.model}` : ""}
                        {row.collapsed ? ` - ${row.descendants} hidden` : ""}
                      </span>
                    </span>
                  </button>
                </div>
                <button
                  type="button"
                  tabIndex={-1}
                  aria-hidden
                  onClick={() => onSelect(span.id)}
                  className="relative h-9 w-full"
                >
                  <span
                    className="absolute top-2.5 h-4 rounded-[4px]"
                    style={{
                      left: `${row.offset * 100}%`,
                      width: `${row.width * 100}%`,
                      background: failed ? "var(--danger)" : SPAN_COLOR[span.kind],
                      opacity: active ? 1 : 0.82,
                    }}
                  />
                  <span
                    className="text-muted-foreground tabular absolute top-2.5 text-[11px] leading-4 whitespace-nowrap"
                    style={
                      row.offset + row.width > 0.78
                        ? { right: `${(1 - row.offset) * 100 + 0.8}%` }
                        : { left: `${(row.offset + row.width) * 100 + 0.8}%` }
                    }
                  >
                    {formatDuration(span.duration_ms)}
                    {Number(span.total_cost) > 0 ? ` - ${formatUsd(span.total_cost)}` : ""}
                  </span>
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
