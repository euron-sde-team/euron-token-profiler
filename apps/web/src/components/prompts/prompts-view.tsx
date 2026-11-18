"use client";

import { Plus, ScrollText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RangeControl } from "@/components/domain/range-control";
import { RelativeTime } from "@/components/domain/relative-time";
import { NewVersionDialog } from "@/components/prompts/new-version-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDuration, formatNumber, formatUsd } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useCan, usePrompts } from "@/lib/queries";
import { rangeOr } from "@/lib/ranges";
import { useUrlParams } from "@/lib/use-url-params";

export function PromptsView() {
  const router = useRouter();
  const { project } = useProject();
  const { get, update } = useUrlParams();
  const range = rangeOr(get("range"), "7d");
  const prompts = usePrompts(project.id, range);
  const canWrite = useCan("member");
  const [creating, setCreating] = useState(false);

  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title="Prompts"
        description="Versioned prompts with what each one costs and how it performs in production."
        actions={
          <>
            <RangeControl
              value={range}
              options={["24h", "7d", "14d", "30d"]}
              onChange={(value) => update({ range: value === "7d" ? null : value })}
            />
            {canWrite ? (
              <Button onClick={() => setCreating(true)}>
                <Plus /> New prompt
              </Button>
            ) : null}
          </>
        }
      />
      {prompts.error ? (
        <ErrorState message={prompts.error.message} onRetry={() => prompts.refetch()} />
      ) : !prompts.data ? (
        <Skeleton className="h-80" />
      ) : prompts.data.items.length === 0 ? (
        <EmptyState
          icon={<ScrollText />}
          title="No prompts yet"
          description="Save a prompt here and fetch it from your SDK, or tag spans with a prompt name and version and they appear on their own."
          action={canWrite ? <Button onClick={() => setCreating(true)}>New prompt</Button> : undefined}
        />
      ) : (
        <TableContainer label="Prompts">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Prompt</TableHead>
                <TableHead>Latest</TableHead>
                <TableHead className="text-right">Calls</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Avg tokens</TableHead>
                <TableHead className="text-right">p95</TableHead>
                <TableHead className="text-right">Errors</TableHead>
                <TableHead className="text-right">Last used</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prompts.data.items.map((prompt) => (
                <TableRow key={prompt.name}>
                  <TableCell className="min-w-48">
                    <Link
                      href={`/prompts/view?name=${encodeURIComponent(prompt.name)}`}
                      className="hover:text-primary font-medium"
                    >
                      {prompt.name}
                    </Link>
                    <span className="text-muted-foreground block text-xs">
                      {prompt.versions} {prompt.versions === 1 ? "version" : "versions"}
                      {prompt.managed ? "" : ", seen in traces only"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex flex-wrap items-center gap-1">
                      v{prompt.latest_version}
                      {prompt.labels.map((label) => (
                        <Badge key={label} tone={label === "production" ? "success" : "info"}>
                          {label}
                        </Badge>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="tabular text-right">{formatNumber(prompt.usage.calls)}</TableCell>
                  <TableCell className="tabular text-right">{formatUsd(prompt.usage.cost)}</TableCell>
                  <TableCell className="tabular text-right">{formatNumber(prompt.usage.avg_tokens)}</TableCell>
                  <TableCell className="tabular text-right">{formatDuration(prompt.usage.p95_ms)}</TableCell>
                  <TableCell className="tabular text-right">
                    <span className={prompt.usage.error_rate >= 5 ? "text-danger" : undefined}>
                      {prompt.usage.error_rate.toFixed(1)}%
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-right">
                    <RelativeTime iso={prompt.usage.last_seen} compact />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <NewVersionDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(name) => router.push(`/prompts/view?name=${encodeURIComponent(name)}`)}
      />
    </PageBody>
  );
}
