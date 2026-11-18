"use client";

import { BreakdownTable } from "@/components/attribution/breakdown-table";
import { PriceTable } from "@/components/attribution/price-table";
import { RangeControl } from "@/components/domain/range-control";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { rangeOr } from "@/lib/ranges";
import { useUrlParams } from "@/lib/use-url-params";

export function ModelsView() {
  const { get, update } = useUrlParams();
  const range = rangeOr(get("range"), "7d");
  const tab = get("tab") === "pricing" ? "pricing" : "usage";
  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title="Models"
        description="What each model costs you in practice, and the price table behind the numbers."
        actions={
          tab === "usage" ? (
            <RangeControl value={range} onChange={(value) => update({ range: value === "7d" ? null : value })} />
          ) : null
        }
      />
      <Tabs value={tab} onValueChange={(value) => update({ tab: value === "usage" ? null : value })}>
        <TabsList>
          <TabsTrigger value="usage">Usage</TabsTrigger>
          <TabsTrigger value="pricing">Pricing</TabsTrigger>
        </TabsList>
        <TabsContent value="usage">
          <BreakdownTable
            dimension="model"
            range={range}
            callsLabel="Calls"
            emptyText="Model calls appear here once a generation span carries a model name."
          />
        </TabsContent>
        <TabsContent value="pricing">
          <PriceTable />
        </TabsContent>
      </Tabs>
    </PageBody>
  );
}
