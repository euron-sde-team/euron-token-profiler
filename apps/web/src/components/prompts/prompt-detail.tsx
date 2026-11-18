"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BarTrend } from "@/components/charts";
import { CodeBlock } from "@/components/copy-field";
import { RangeControl } from "@/components/domain/range-control";
import { NewVersionDialog } from "@/components/prompts/new-version-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { StatCard } from "@/components/ui/stat-card";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, formatDuration, formatNumber, formatUsd } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useCan, useMoveLabel, usePrompt } from "@/lib/queries";
import { rangeOr } from "@/lib/ranges";
import { useUrlParams } from "@/lib/use-url-params";

export function PromptDetailView() {
  const { project } = useProject();
  const { get, update } = useUrlParams();
  const name = get("name") ?? "";
  const range = rangeOr(get("range"), "7d");
  const prompt = usePrompt(project.id, name, range);
  const canWrite = useCan("member");
  const move = useMoveLabel();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  if (prompt.error) {
    return (
      <PageBody>
        <ErrorState title="Prompt not found" message={prompt.error.message} />
      </PageBody>
    );
  }
  if (!prompt.data) {
    return (
      <PageBody>
        <Skeleton className="h-96" />
      </PageBody>
    );
  }
  const { versions, usage } = prompt.data;
  const latest = versions[0];
  const shown = versions.find((v) => v.version === open) ?? latest;
  const chart = [...versions]
    .reverse()
    .filter((v) => v.usage.calls > 0)
    .map((v) => ({
      version: `v${v.version}`,
      cost: v.usage.calls ? (Number(v.usage.cost) / v.usage.calls) * 1000 : 0,
      tokens: v.usage.avg_tokens,
    }));

  async function promote(version: number) {
    await move.mutateAsync({ project: project.id, name, label: "production", version });
    toast.success(`Version ${version} is now production`);
  }

  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title={name}
        breadcrumbs={[{ label: "Prompts", href: "/prompts" }, { label: name }]}
        description={`${versions.length} ${versions.length === 1 ? "version" : "versions"}. Usage covers the selected range.`}
        actions={
          <>
            <RangeControl
              value={range}
              options={["24h", "7d", "14d", "30d"]}
              onChange={(value) => update({ range: value === "7d" ? null : value })}
            />
            {canWrite ? (
              <Button onClick={() => setCreating(true)}>
                <Plus /> New version
              </Button>
            ) : null}
          </>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Calls" value={formatNumber(usage.calls)} caption={`${usage.error_rate.toFixed(1)}% failed`} />
        <StatCard
          label="Cost"
          value={formatUsd(usage.cost)}
          caption={`${formatUsd(usage.calls ? Number(usage.cost) / usage.calls : 0)} per call`}
        />
        <StatCard label="Avg tokens per call" value={formatNumber(usage.avg_tokens)} />
        <StatCard
          label="p95 latency"
          value={formatDuration(usage.p95_ms)}
          caption={`p50 ${formatDuration(usage.p50_ms)}`}
        />
      </div>
      {chart.length > 1 ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Cost per 1,000 calls by version</CardTitle>
            <CardDescription>How each version compares when it ran in this range.</CardDescription>
          </CardHeader>
          <CardContent>
            <BarTrend
              label="Cost per 1,000 calls for each prompt version"
              data={chart}
              xKey="version"
              yFormat={(v) => formatUsd(v)}
              yWidth={56}
              decimals
              height={200}
              series={[{ key: "cost", name: "Cost per 1,000 calls", color: "var(--series-1)" }]}
            />
          </CardContent>
        </Card>
      ) : null}
      <TableContainer label="Prompt versions" className="mb-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Version</TableHead>
              <TableHead>Labels</TableHead>
              <TableHead className="text-right">Calls</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">Avg tokens</TableHead>
              <TableHead className="text-right">p95</TableHead>
              <TableHead className="text-right">Errors</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {versions.map((v) => (
              <TableRow key={v.version} data-state={shown?.version === v.version ? "selected" : undefined}>
                <TableCell>
                  <button
                    type="button"
                    onClick={() => setOpen(v.version)}
                    className="hover:text-primary text-left font-medium"
                  >
                    v{v.version}
                  </button>
                  <span className="text-muted-foreground block text-xs">
                    {v.commit_message ?? (v.managed ? formatDateTime(v.created_at) : "seen in traces")}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="inline-flex flex-wrap gap-1">
                    {v.labels.map((label) => (
                      <Badge key={label} tone={label === "production" ? "success" : "info"}>
                        {label}
                      </Badge>
                    ))}
                  </span>
                </TableCell>
                <TableCell className="tabular text-right">{formatNumber(v.usage.calls)}</TableCell>
                <TableCell className="tabular text-right">{formatUsd(v.usage.cost)}</TableCell>
                <TableCell className="tabular text-right">{formatNumber(v.usage.avg_tokens)}</TableCell>
                <TableCell className="tabular text-right">{formatDuration(v.usage.p95_ms)}</TableCell>
                <TableCell className="tabular text-right">{v.usage.error_rate.toFixed(1)}%</TableCell>
                <TableCell className="text-right">
                  {canWrite && v.managed && !v.labels.includes("production") ? (
                    <Button size="sm" variant="secondary" loading={move.isPending} onClick={() => promote(v.version)}>
                      Make production
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {shown ? (
        <Card>
          <CardHeader>
            <CardTitle>Version {shown.version} template</CardTitle>
            <CardDescription>
              {shown.template
                ? "Fetch it with the SDK: profiler.get_prompt(name, version=...)."
                : "This version was first seen in traces; its text was never saved here."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {shown.template ? <CodeBlock code={shown.template} label={`Template of version ${shown.version}`} /> : null}
          </CardContent>
        </Card>
      ) : null}
      <NewVersionDialog
        key={latest?.version}
        open={creating}
        onOpenChange={setCreating}
        name={name}
        template={latest?.template ?? ""}
      />
    </PageBody>
  );
}
