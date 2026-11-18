"use client";

import { BreakdownTable } from "@/components/attribution/breakdown-table";
import { RangeControl } from "@/components/domain/range-control";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { rangeOr } from "@/lib/ranges";
import { useUrlParams } from "@/lib/use-url-params";

export function AgentsView() {
  const { get, update } = useUrlParams();
  const range = rangeOr(get("range"), "7d");
  const tab = get("tab") === "tools" ? "tools" : "agents";
  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title="Agents and tools"
        description="Each agent run and tool call, with the tokens and dollars of every model call made inside it."
        actions={<RangeControl value={range} onChange={(value) => update({ range: value === "7d" ? null : value })} />}
      />
      <Tabs value={tab} onValueChange={(value) => update({ tab: value === "agents" ? null : value })}>
        <TabsList>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
        </TabsList>
        <TabsContent value="agents">
          <p className="text-muted-foreground mb-3 text-[13px]">
            Cost and tokens count every model call below an agent run, including those inside its tools.
          </p>
          <BreakdownTable
            dimension="agent"
            range={range}
            callsLabel="Runs"
            emptyText="Name an agent with kind=agent spans or the gen_ai.agent.name attribute."
          />
        </TabsContent>
        <TabsContent value="tools">
          <p className="text-muted-foreground mb-3 text-[13px]">
            A tool call costs what the model calls made inside it cost (a summariser, an embedding). Latency and errors
            are the tool&apos;s own.
          </p>
          <BreakdownTable
            dimension="tool"
            range={range}
            callsLabel="Calls"
            emptyText="Wrap a function call in a tool span, or set gen_ai.tool.name."
          />
        </TabsContent>
      </Tabs>
    </PageBody>
  );
}
