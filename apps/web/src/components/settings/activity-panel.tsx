"use client";

import { useState } from "react";

import { RelativeTime } from "@/components/domain/relative-time";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Pagination } from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AUDIT_LABEL } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useAudit } from "@/lib/queries";
import { humanize } from "@/lib/format";

const PAGE = 15;

function detail(details: Record<string, unknown>): string {
  const entries = Object.entries(details).filter(([, value]) => typeof value !== "object" || value === null);
  return entries.map(([key, value]) => `${humanize(key)}: ${String(value)}`).join(", ");
}

export function ActivityPanel() {
  const { project } = useProject();
  const [offset, setOffset] = useState(0);
  const audit = useAudit(project.id, { limit: PAGE, offset });
  if (audit.error) return <ErrorState message={audit.error.message} onRetry={() => audit.refetch()} />;
  if (!audit.data) return <Skeleton className="h-80" />;
  return (
    <div>
      <p className="text-muted-foreground mb-3 text-[13px]">Who changed what in {project.name}, newest first.</p>
      <TableContainer label="Activity">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Change</TableHead>
              <TableHead>Details</TableHead>
              <TableHead className="text-right">When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {audit.data.items.map((event) => (
              <TableRow key={event.id}>
                <TableCell>
                  <span className="font-medium">{event.actor_name ?? "System"}</span>{" "}
                  <span className="text-muted-foreground">{AUDIT_LABEL[event.action] ?? event.action}</span>
                </TableCell>
                <TableCell className="text-muted-foreground max-w-96 truncate" title={detail(event.details)}>
                  {detail(event.details)}
                </TableCell>
                <TableCell className="text-muted-foreground text-right">
                  <RelativeTime iso={event.created_at} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Pagination
        className="mt-4"
        total={audit.data.total}
        limit={PAGE}
        offset={offset}
        onOffsetChange={setOffset}
        noun="events"
      />
    </div>
  );
}
