"use client";

import Link from "next/link";

import { KindBadge, StatusBadge } from "@/components/domain/badges";
import { CodeBlock } from "@/components/copy-field";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDuration, formatNumber, formatUsd } from "@/lib/format";
import type { Span } from "@/lib/types";

/** Pretty-print stored payloads that are JSON; show anything else as the text it is. */
export function prettyPayload(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground text-[11.5px]">{label}</dt>
      <dd className="tabular truncate text-[13px] font-medium">{value}</dd>
    </div>
  );
}

const COST_SOURCE: Record<string, string> = {
  reported: "reported by the caller",
  table: "from the price table",
  none: "no price for this model",
};

export function SpanPanel({ span }: { span: Span }) {
  const metered = span.kind === "generation" || span.kind === "embedding";
  return (
    <Card>
      <CardHeader className="gap-2 pb-0">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-[15px]">{span.name}</CardTitle>
          <KindBadge kind={span.kind} />
          <StatusBadge status={span.status} />
          {span.usage_estimated ? <Badge tone="warning">Tokens estimated</Badge> : null}
          {span.redactions > 0 ? <Badge tone="info">{span.redactions} values redacted</Badge> : null}
        </div>
        {span.status_message ? <p className="text-danger text-[13px]">{span.status_message}</p> : null}
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <Stat label="Duration" value={formatDuration(span.duration_ms)} />
          {span.time_to_first_token_ms !== null ? (
            <Stat label="Time to first token" value={formatDuration(span.time_to_first_token_ms)} />
          ) : null}
          {span.model ? <Stat label="Model" value={span.model} /> : null}
          {span.provider ? <Stat label="Provider" value={span.provider} /> : null}
          {metered ? (
            <>
              <Stat label="Input tokens" value={formatNumber(span.input_tokens)} />
              <Stat label="Output tokens" value={formatNumber(span.output_tokens)} />
              {span.cached_tokens > 0 ? <Stat label="Cached input" value={formatNumber(span.cached_tokens)} /> : null}
              <Stat label="Input cost" value={formatUsd(span.input_cost)} />
              <Stat label="Output cost" value={formatUsd(span.output_cost)} />
              <Stat label="Total cost" value={formatUsd(span.total_cost)} />
            </>
          ) : null}
          {span.agent_name ? <Stat label="Agent" value={span.agent_name} /> : null}
          {span.tool_name ? <Stat label="Tool" value={span.tool_name} /> : null}
          {span.prompt_name ? (
            <Stat
              label="Prompt"
              value={
                <Link
                  href={`/prompts/view?name=${encodeURIComponent(span.prompt_name)}`}
                  className="text-primary hover:underline"
                >
                  {span.prompt_name} v{span.prompt_version}
                </Link>
              }
            />
          ) : null}
        </dl>
        {metered && span.cost_source ? (
          <p className="text-muted-foreground mt-3 text-xs">Cost {COST_SOURCE[span.cost_source]}.</p>
        ) : null}
        <Tabs defaultValue="input" className="mt-4">
          <TabsList>
            <TabsTrigger value="input">Input</TabsTrigger>
            <TabsTrigger value="output">Output</TabsTrigger>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
          </TabsList>
          <TabsContent value="input">
            {span.input ? (
              <CodeBlock code={prettyPayload(span.input)} label="Span input" className="max-h-80 overflow-auto" />
            ) : (
              <p className="text-muted-foreground text-[13px]">No input was stored for this span.</p>
            )}
          </TabsContent>
          <TabsContent value="output">
            {span.output ? (
              <CodeBlock code={prettyPayload(span.output)} label="Span output" className="max-h-80 overflow-auto" />
            ) : (
              <p className="text-muted-foreground text-[13px]">
                {span.status === "error"
                  ? "The span failed before producing output."
                  : "No output was stored for this span."}
              </p>
            )}
          </TabsContent>
          <TabsContent value="metadata">
            <CodeBlock
              code={JSON.stringify(
                { ...span.metadata, model_parameters: span.model_parameters, level: span.level },
                null,
                2,
              )}
              label="Span metadata"
              className="max-h-80 overflow-auto"
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
