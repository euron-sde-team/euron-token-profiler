"use client";

import Link from "next/link";
import { useMemo } from "react";

import { StatusBadge } from "@/components/domain/badges";
import { CopyButton } from "@/components/copy-field";
import { SpanPanel } from "@/components/traces/span-panel";
import { Waterfall } from "@/components/traces/waterfall";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { ApiError } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, formatUsd } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useTrace } from "@/lib/queries";
import { buildRows } from "@/lib/tree";
import { useUrlParams } from "@/lib/use-url-params";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground text-[11.5px]">{label}</dt>
      <dd className="tabular text-[14px] font-semibold break-words">{children}</dd>
    </div>
  );
}

export function TraceDetailView({ id }: { id: string }) {
  const { project } = useProject();
  const { get, update } = useUrlParams();
  const trace = useTrace(project.id, id);
  const spans = trace.data?.spans;
  const selected = useMemo(() => {
    if (!spans?.length) return null;
    const wanted = get("span");
    if (wanted && spans.some((s) => s.id === wanted)) return wanted;
    // Open on the first failing span when there is one, otherwise on the root.
    return spans.find((s) => s.status === "error")?.id ?? buildRows(spans)[0]?.span.id ?? null;
  }, [spans, get]);

  if (trace.error) {
    const missing = trace.error instanceof ApiError && trace.error.status === 404;
    return (
      <PageBody>
        <ErrorState
          title={missing ? "Trace not found" : "Could not load this trace"}
          message={trace.error.message}
          onRetry={missing ? undefined : () => trace.refetch()}
        />
      </PageBody>
    );
  }
  if (!trace.data) {
    return (
      <PageBody>
        <Skeleton className="mb-4 h-24" />
        <Skeleton className="h-96" />
      </PageBody>
    );
  }
  const { trace: t } = trace.data;
  const span = trace.data.spans.find((s) => s.id === selected);

  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title={t.name || "Untitled trace"}
        breadcrumbs={[{ label: "Traces", href: "/traces" }, { label: t.name || t.id.slice(0, 8) }]}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{t.id}</span>
            <CopyButton value={t.id} label="Copy id" />
          </span>
        }
        actions={<StatusBadge status={t.status} />}
      />
      <Card className="mb-4">
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 xl:grid-cols-8">
            <Fact label="Duration">{formatDuration(t.duration_ms)}</Fact>
            <Fact label="Cost">{formatUsd(t.total_cost)}</Fact>
            <Fact label="Input tokens">{formatNumber(t.input_tokens)}</Fact>
            <Fact label="Output tokens">{formatNumber(t.output_tokens)}</Fact>
            <Fact label="Spans">
              {formatNumber(t.span_count)}
              {t.error_count > 0 ? <span className="text-danger text-xs"> ({t.error_count} failed)</span> : null}
            </Fact>
            <Fact label="Model calls">{formatNumber(t.generation_count)}</Fact>
            <Fact label="Started">{formatDateTime(t.started_at)}</Fact>
            <Fact label="Environment">{t.environment}</Fact>
          </dl>
          <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[13px]">
            {t.user_id ? (
              <Link href={`/traces?user_id=${encodeURIComponent(t.user_id)}`}>
                <Badge tone="outline">User {t.user_id}</Badge>
              </Link>
            ) : null}
            {t.session_id ? (
              <Link href={`/traces?session_id=${encodeURIComponent(t.session_id)}`}>
                <Badge tone="outline">Session {t.session_id}</Badge>
              </Link>
            ) : null}
            {t.release ? <Badge tone="outline">Release {t.release}</Badge> : null}
            {t.agents.map((name) => (
              <Badge key={name} tone="warning">
                {name}
              </Badge>
            ))}
            {t.tools.map((name) => (
              <Badge key={name} tone="success">
                {name}
              </Badge>
            ))}
            {t.models.map((name) => (
              <Badge key={name} tone="primary">
                {name}
              </Badge>
            ))}
            {t.tags.map((name) => (
              <Badge key={name} tone="neutral">
                #{name}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Waterfall
          spans={trace.data.spans}
          durationMs={Math.max(1, t.duration_ms)}
          selected={selected}
          onSelect={(spanId) => update({ span: spanId })}
        />
        {span ? <SpanPanel span={span} /> : null}
      </div>
    </PageBody>
  );
}
