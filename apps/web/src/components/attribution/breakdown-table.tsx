"use client";

import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDuration, formatNumber, formatTokens, formatUsd } from "@/lib/format";
import { DIMENSION_LABEL } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useBreakdown } from "@/lib/queries";
import type { BreakdownItem, Dimension } from "@/lib/types";
import { RelativeTime } from "@/components/domain/relative-time";

/** Where the cost went: one row per model, agent, tool or prompt, with a bar for its share. */
export function BreakdownTable({
  dimension,
  range,
  callsLabel,
  emptyText,
  keyCell,
}: {
  dimension: Dimension;
  range: string;
  callsLabel: string;
  emptyText: string;
  keyCell?: (item: BreakdownItem) => React.ReactNode;
}) {
  const { project } = useProject();
  const data = useBreakdown(project.id, dimension, range);
  if (data.error) return <ErrorState message={data.error.message} onRetry={() => data.refetch()} />;
  if (!data.data) return <Skeleton className="h-80" />;
  if (data.data.items.length === 0)
    return <EmptyState title={`No ${dimension}s in this range`} description={emptyText} />;
  return (
    <TableContainer label={`${DIMENSION_LABEL[dimension]} breakdown`}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{DIMENSION_LABEL[dimension]}</TableHead>
            <TableHead className="text-right">{callsLabel}</TableHead>
            <TableHead className="text-right">Tokens in / out</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead className="min-w-36">Share</TableHead>
            <TableHead className="text-right">p50</TableHead>
            <TableHead className="text-right">p95</TableHead>
            <TableHead className="text-right">Errors</TableHead>
            <TableHead className="text-right">Last seen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.data.items.map((item) => (
            <TableRow key={`${item.key}-${item.version ?? ""}`}>
              <TableCell className="min-w-40 font-medium">{keyCell ? keyCell(item) : item.key}</TableCell>
              <TableCell className="tabular text-right">{formatNumber(item.calls)}</TableCell>
              <TableCell className="tabular text-right">
                {formatTokens(item.input_tokens)} / {formatTokens(item.output_tokens)}
              </TableCell>
              <TableCell className="tabular text-right">
                {formatUsd(item.cost)}
                <span className="text-muted-foreground block text-xs">
                  {item.calls > 0 ? `${formatUsd(item.avg_cost_per_call)} per call` : ""}
                </span>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="bg-muted h-1.5 flex-1 rounded-full">
                    <div
                      className="bg-primary h-1.5 rounded-full"
                      style={{ width: `${Math.max(item.cost_share > 0 ? 2 : 0, item.cost_share * 100)}%` }}
                    />
                  </div>
                  <span className="tabular text-muted-foreground w-9 text-right text-xs">
                    {Math.round(item.cost_share * 100)}%
                  </span>
                </div>
              </TableCell>
              <TableCell className="tabular text-right">{formatDuration(item.p50_ms)}</TableCell>
              <TableCell className="tabular text-right">{formatDuration(item.p95_ms)}</TableCell>
              <TableCell className="tabular text-right">
                <span className={item.error_rate >= 5 ? "text-danger" : undefined}>{item.error_rate.toFixed(1)}%</span>
              </TableCell>
              <TableCell className="text-muted-foreground text-right">
                <RelativeTime iso={item.last_seen} compact />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
