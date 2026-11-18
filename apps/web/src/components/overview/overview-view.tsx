"use client";

import { Activity, AlertTriangle, Coins, Gauge, Hash } from "lucide-react";
import Link from "next/link";

import { AreaTrend, BarTrend, SERIES } from "@/components/charts";
import { Delta } from "@/components/domain/delta";
import { RangeControl } from "@/components/domain/range-control";
import { RelativeTime } from "@/components/domain/relative-time";
import { StatusBadge } from "@/components/domain/badges";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { StatCard } from "@/components/ui/stat-card";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatBucket, formatCompact, formatDuration, formatNumber, formatTokens, formatUsd } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useBreakdown, useFacets, useOverview, useTraces } from "@/lib/queries";
import { rangeOr } from "@/lib/ranges";
import { useUrlParams } from "@/lib/use-url-params";
import type { Overview } from "@/lib/types";

function Kpis({ data }: { data: Overview }) {
  const { current: now, previous: before } = data;
  // A period that began before the first trace was recorded has nothing to compare with.
  const comparable = before.traces >= Math.max(5, now.traces * 0.1);
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <StatCard
        label="Traces"
        value={formatNumber(now.traces)}
        icon={<Activity />}
        caption={<Delta current={now.traces} previous={before.traces} higherIsBetter comparable={comparable} />}
      />
      <StatCard
        label="Cost"
        value={formatUsd(now.cost)}
        icon={<Coins />}
        caption={
          <>
            <Delta current={Number(now.cost)} previous={Number(before.cost)} comparable={comparable} />
            <span className="block">{formatUsd(now.avg_cost_per_trace)} per trace</span>
          </>
        }
      />
      <StatCard
        label="Tokens"
        value={formatTokens(now.input_tokens + now.output_tokens)}
        icon={<Hash />}
        caption={
          <>
            <Delta
              current={now.input_tokens + now.output_tokens}
              previous={before.input_tokens + before.output_tokens}
              comparable={comparable}
            />
            <span className="block">
              {formatTokens(now.input_tokens)} in, {formatTokens(now.output_tokens)} out
            </span>
          </>
        }
      />
      <StatCard
        label="Latency p95"
        value={formatDuration(now.p95_ms)}
        icon={<Gauge />}
        caption={
          <>
            <Delta current={now.p95_ms} previous={before.p95_ms} comparable={comparable} />
            <span className="block">
              p50 {formatDuration(now.p50_ms)}, p99 {formatDuration(now.p99_ms)}
            </span>
          </>
        }
      />
      <StatCard
        label="Error rate"
        value={`${now.error_rate.toFixed(now.error_rate < 10 ? 1 : 0)}%`}
        icon={<AlertTriangle />}
        caption={
          <>
            <Delta current={now.error_rate} previous={before.error_rate} comparable={comparable} />
            <span className="block">{formatNumber(now.errors)} failed traces</span>
          </>
        }
      />
    </div>
  );
}

function Charts({ data }: { data: Overview }) {
  const xFormat = (value: string) => formatBucket(value, data.bucket_seconds);
  const cost = data.cost_by_model.map((point) => ({
    at: point.at,
    ...Object.fromEntries(data.top_models.map((model) => [model, Number(point.values[model] ?? 0)])),
  }));
  const series = data.series.map((p) => ({ ...p, cost: Number(p.cost) }));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Cost over time</CardTitle>
          <CardDescription>Spend per period, split by the models that cost the most.</CardDescription>
        </CardHeader>
        <CardContent>
          <BarTrend
            label="Cost over time, stacked by model"
            data={cost}
            xKey="at"
            xFormat={xFormat}
            stacked
            yFormat={(v) => formatUsd(v)}
            yWidth={56}
            decimals
            series={data.top_models.map((model, index) => ({
              key: model,
              name: model,
              color: model === "other" ? "var(--series-6)" : SERIES[index % SERIES.length],
            }))}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Latency</CardTitle>
          <CardDescription>Trace duration, median and 95th percentile.</CardDescription>
        </CardHeader>
        <CardContent>
          <AreaTrend
            label="Trace latency percentiles over time"
            data={series}
            xKey="at"
            xFormat={xFormat}
            yFormat={formatDuration}
            yWidth={52}
            series={[
              { key: "p95_ms", name: "p95", color: "var(--series-3)" },
              { key: "p50_ms", name: "p50", color: "var(--series-1)" },
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Tokens</CardTitle>
          <CardDescription>Prompt and completion tokens per period.</CardDescription>
        </CardHeader>
        <CardContent>
          <AreaTrend
            label="Input and output tokens over time"
            data={series}
            xKey="at"
            xFormat={xFormat}
            stacked
            yFormat={formatCompact}
            series={[
              { key: "input_tokens", name: "Input", color: "var(--series-2)" },
              { key: "output_tokens", name: "Output", color: "var(--series-1)" },
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Traces and errors</CardTitle>
          <CardDescription>Requests per period, with the failing ones on top.</CardDescription>
        </CardHeader>
        <CardContent>
          <BarTrend
            label="Traces and errors over time"
            data={series.map((p) => ({ ...p, ok: p.traces - p.errors }))}
            xKey="at"
            xFormat={xFormat}
            stacked
            yFormat={formatCompact}
            series={[
              { key: "ok", name: "OK", color: "var(--series-1)" },
              { key: "errors", name: "Errors", color: "var(--danger)" },
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function TopList({ dimension, title, href }: { dimension: "model" | "agent"; title: string; href: string }) {
  const { project } = useProject();
  const { get } = useUrlParams();
  const range = rangeOr(get("range"), "24h");
  const data = useBreakdown(project.id, dimension, range);
  const rows = (data.data?.items ?? []).slice(0, 5);
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>Share of spend in this range.</CardDescription>
        </div>
        <Link href={href} className="text-primary text-[13px] hover:underline">
          See all
        </Link>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-muted-foreground text-[13px]">Nothing recorded in this range.</p>
        ) : (
          <ul className="space-y-3">
            {rows.map((row) => (
              <li key={row.key}>
                <div className="flex items-baseline justify-between gap-3 text-[13px]">
                  <span className="truncate font-medium">{row.key}</span>
                  <span className="tabular text-muted-foreground shrink-0">
                    {formatUsd(row.cost)} <span className="text-subtle">({Math.round(row.cost_share * 100)}%)</span>
                  </span>
                </div>
                <div className="bg-muted mt-1 h-1.5 rounded-full">
                  <div
                    className="bg-primary h-1.5 rounded-full"
                    style={{ width: `${Math.max(2, row.cost_share * 100)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RecentErrors({ range }: { range: string }) {
  const { project } = useProject();
  const traces = useTraces(project.id, { range, status: "error", limit: 6 });
  const rows = traces.data?.items ?? [];
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Recent failures</CardTitle>
          <CardDescription>The latest traces with an error span.</CardDescription>
        </div>
        <Link href="/traces?status=error" className="text-primary text-[13px] hover:underline">
          See all
        </Link>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-muted-foreground text-[13px]">No failing traces in this range.</p>
        ) : (
          <TableContainer label="Recent failing traces" className="border-0 shadow-none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Trace</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((trace) => (
                  <TableRow key={trace.id}>
                    <TableCell>
                      <Link href={`/traces/${trace.id}`} className="hover:text-primary font-medium">
                        {trace.name || trace.id.slice(0, 8)}
                      </Link>
                      <span className="text-muted-foreground block text-xs">
                        {trace.agents[0] ?? trace.tools[0] ?? "no agent"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={trace.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-right">
                      <RelativeTime iso={trace.started_at} compact />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}

export function OverviewView() {
  const { project } = useProject();
  const { get, update } = useUrlParams();
  const range = rangeOr(get("range"), "24h");
  const environment = get("environment") ?? undefined;
  const overview = useOverview(project.id, range, environment);
  const facets = useFacets(project.id);
  const environments = facets.data?.environments ?? [];

  return (
    <PageBody>
      <PageHeader
        title="Overview"
        description={`How ${project.name} is doing: cost, tokens, latency and failures against the previous period.`}
        actions={
          <>
            {environments.length > 1 ? (
              <NativeSelect
                aria-label="Environment"
                className="h-8 w-48 text-[13px]"
                value={environment ?? ""}
                onChange={(event) => update({ environment: event.target.value || null })}
              >
                <option value="">All environments</option>
                {environments.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </NativeSelect>
            ) : null}
            <RangeControl value={range} onChange={(value) => update({ range: value === "24h" ? null : value })} />
          </>
        }
      />
      {overview.error ? (
        <ErrorState message={overview.error.message} onRetry={() => overview.refetch()} />
      ) : !overview.data ? (
        <div className="space-y-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-80" />
        </div>
      ) : overview.data.current.traces === 0 && overview.data.previous.traces === 0 ? (
        <EmptyState
          title="No traces yet"
          description="Send a trace with the Python SDK or an OpenTelemetry exporter and it shows up here within a minute."
          action={
            <Link href="/keys" className="text-primary text-[13px] hover:underline">
              Create an API key
            </Link>
          }
        />
      ) : (
        <div className="space-y-6">
          <Kpis data={overview.data} />
          <Charts data={overview.data} />
          <div className="grid gap-4 lg:grid-cols-3">
            <TopList dimension="model" title="Top models" href="/models" />
            <TopList dimension="agent" title="Top agents" href="/agents" />
            <RecentErrors range={range} />
          </div>
          <p className="text-muted-foreground text-xs">
            Aggregates are cached for 30 seconds{overview.data.cached ? " (this view came from the cache)" : ""}.
            Computed <RelativeTime iso={overview.data.generated_at} />.
          </p>
        </div>
      )}
    </PageBody>
  );
}
