"use client";

import { Download } from "lucide-react";

import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiUrl, toQuery, V1 } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useArchives } from "@/lib/queries";

export function ArchivesPanel() {
  const { project } = useProject();
  const archives = useArchives(project.id);
  if (archives.error) return <ErrorState message={archives.error.message} onRetry={() => archives.refetch()} />;
  if (!archives.data) return <Skeleton className="h-48" />;
  if (archives.data.length === 0) {
    return (
      <EmptyState
        title="Nothing archived yet"
        description={
          project.archive_before_delete
            ? `Traces older than ${project.retention_days} days are written here (gzip NDJSON) before they are deleted.`
            : "Turn on archive before delete in the project settings to keep expired traces."
        }
      />
    );
  }
  return (
    <TableContainer label="Archive objects">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Object</TableHead>
            <TableHead className="text-right">Size</TableHead>
            <TableHead className="text-right">Download</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {archives.data.map((item) => (
            <TableRow key={item.key}>
              <TableCell className="font-mono text-xs">{item.key}</TableCell>
              <TableCell className="tabular text-right">{formatBytes(item.size_bytes)}</TableCell>
              <TableCell className="text-right">
                <a
                  className="text-primary inline-flex items-center gap-1 hover:underline"
                  href={apiUrl(`${V1}/projects/${project.id}/archives/download${toQuery({ key: item.key })}`)}
                >
                  <Download className="size-3.5" aria-hidden /> Download
                </a>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
