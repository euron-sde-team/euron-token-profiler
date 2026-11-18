"use client";

import { ListTree } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/domain/badges";
import { RangeControl } from "@/components/domain/range-control";
import { RelativeTime } from "@/components/domain/relative-time";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { FilterBar, SearchField } from "@/components/ui/filter-bar";
import { NativeSelect } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDuration, formatNumber, formatTokens, formatUsd } from "@/lib/format";
import { useProject } from "@/lib/project";
import { useFacets, useTraces } from "@/lib/queries";
import { rangeOr } from "@/lib/ranges";
import { useDebouncedValue } from "@/lib/use-debounced";
import { useUrlParams } from "@/lib/use-url-params";

const PAGE = 25;
const SORTS = [
  { value: "started_at", label: "Newest" },
  { value: "cost", label: "Most expensive" },
  { value: "duration", label: "Slowest" },
  { value: "tokens", label: "Most tokens" },
];

function Select({
  label,
  value,
  options,
  onChange,
  all,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  all: string;
}) {
  return (
    <NativeSelect
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-9 w-auto max-w-44 text-[13px]"
    >
      <option value="">{all}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </NativeSelect>
  );
}

export function TracesView() {
  const router = useRouter();
  const { project } = useProject();
  const { get, update } = useUrlParams();
  const [search, setSearch] = useState(get("q") ?? "");
  const debounced = useDebouncedValue(search, 300);
  useEffect(() => {
    if (debounced !== (get("q") ?? "")) update({ q: debounced || null, offset: null });
    // `get` and `update` are re-created on every render; only the typed text matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const range = rangeOr(get("range"), "24h");
  const offset = Number(get("offset") ?? 0) || 0;
  const filters = {
    status: get("status") ?? "",
    model: get("model") ?? "",
    agent: get("agent") ?? "",
    tool: get("tool") ?? "",
    prompt: get("prompt") ?? "",
    environment: get("environment") ?? "",
    user_id: get("user_id") ?? "",
    session_id: get("session_id") ?? "",
  };
  const sort = get("sort") ?? "started_at";
  const traces = useTraces(project.id, {
    range,
    q: get("q") ?? "",
    ...filters,
    sort,
    order: "desc",
    limit: PAGE,
    offset,
  });
  const facets = useFacets(project.id);
  const set = (key: string) => (value: string) => update({ [key]: value || null, offset: null });
  const active = Object.values(filters).some(Boolean) || Boolean(get("q"));
  const data = traces.data;

  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title="Traces"
        description="Every request through your application, with its cost, tokens and the agents, tools and models it touched."
        actions={
          <RangeControl
            value={range}
            onChange={(value) => update({ range: value === "24h" ? null : value, offset: null })}
          />
        }
      />
      <FilterBar className="mb-4">
        <SearchField
          value={search}
          onChange={setSearch}
          label="Search traces"
          placeholder="Name, trace id, user or session"
        />
        <NativeSelect
          aria-label="Status"
          value={filters.status}
          onChange={(event) => set("status")(event.target.value)}
          className="h-9 w-auto text-[13px]"
        >
          <option value="">Any status</option>
          <option value="ok">OK</option>
          <option value="error">Errors</option>
        </NativeSelect>
        <Select
          label="Model"
          value={filters.model}
          options={facets.data?.models ?? []}
          onChange={set("model")}
          all="Any model"
        />
        <Select
          label="Agent"
          value={filters.agent}
          options={facets.data?.agents ?? []}
          onChange={set("agent")}
          all="Any agent"
        />
        <Select
          label="Tool"
          value={filters.tool}
          options={facets.data?.tools ?? []}
          onChange={set("tool")}
          all="Any tool"
        />
        <Select
          label="Prompt"
          value={filters.prompt}
          options={facets.data?.prompts ?? []}
          onChange={set("prompt")}
          all="Any prompt"
        />
        <Select
          label="Environment"
          value={filters.environment}
          options={facets.data?.environments ?? []}
          onChange={set("environment")}
          all="Any environment"
        />
        <NativeSelect
          aria-label="Sort"
          value={sort}
          onChange={(event) =>
            update({ sort: event.target.value === "started_at" ? null : event.target.value, offset: null })
          }
          className="h-9 w-auto text-[13px]"
        >
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
        {active ? (
          <button
            type="button"
            className="text-primary text-[13px] hover:underline"
            onClick={() => {
              setSearch("");
              router.replace("/traces");
            }}
          >
            Clear filters
          </button>
        ) : null}
      </FilterBar>
      {filters.user_id || filters.session_id ? (
        <p className="text-muted-foreground mb-3 text-[13px]">
          Showing {filters.user_id ? `user ${filters.user_id}` : `session ${filters.session_id}`}.
        </p>
      ) : null}

      {traces.error ? (
        <ErrorState message={traces.error.message} onRetry={() => traces.refetch()} />
      ) : !data ? (
        <Skeleton className="h-96" />
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={<ListTree />}
          title={active ? "No traces match these filters" : "No traces in this range"}
          description={
            active
              ? "Loosen a filter or widen the time range."
              : "Widen the time range, or send a trace with an SDK or OpenTelemetry."
          }
        />
      ) : (
        <>
          <TableContainer label="Traces">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Trace</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Agent and models</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead className="text-right">Started</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((trace) => (
                  <TableRow key={trace.id}>
                    <TableCell className="min-w-48">
                      <Link href={`/traces/${trace.id}`} className="hover:text-primary font-medium">
                        {trace.name || "Untitled trace"}
                      </Link>
                      <span className="text-muted-foreground block font-mono text-[11.5px]">
                        {trace.id.slice(0, 12)} - {formatNumber(trace.span_count)} spans
                      </span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={trace.status} />
                    </TableCell>
                    <TableCell className="max-w-64">
                      <div className="flex flex-wrap gap-1">
                        {trace.agents.slice(0, 1).map((agent) => (
                          <Badge key={agent} tone="warning">
                            {agent}
                          </Badge>
                        ))}
                        {trace.models.slice(0, 2).map((model) => (
                          <Badge key={model} tone="outline">
                            {model}
                          </Badge>
                        ))}
                        {trace.models.length > 2 ? <Badge tone="neutral">+{trace.models.length - 2}</Badge> : null}
                      </div>
                    </TableCell>
                    <TableCell className="tabular text-right">{formatDuration(trace.duration_ms)}</TableCell>
                    <TableCell className="tabular text-right">{formatTokens(trace.total_tokens)}</TableCell>
                    <TableCell className="tabular text-right">{formatUsd(trace.total_cost)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {trace.user_id ? (
                        <Link
                          href={`/traces?user_id=${encodeURIComponent(trace.user_id)}`}
                          className="hover:text-primary"
                        >
                          {trace.user_id}
                        </Link>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-right whitespace-nowrap">
                      <RelativeTime iso={trace.started_at} compact />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Pagination
            className="mt-4"
            total={data.total}
            limit={PAGE}
            offset={offset}
            noun={data.total_capped ? "traces (at least)" : "traces"}
            onOffsetChange={(next) => update({ offset: next || null })}
          />
        </>
      )}
    </PageBody>
  );
}
