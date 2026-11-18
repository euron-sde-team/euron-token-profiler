import { Badge } from "@/components/ui/badge";
import { BUDGET_STATE, SEVERITY, SPAN_KIND } from "@/lib/labels";
import type { Budget, SpanKind } from "@/lib/types";

export function StatusBadge({ status }: { status: "ok" | "error" }) {
  return status === "error" ? <Badge tone="danger">Error</Badge> : <Badge tone="success">OK</Badge>;
}

export function KindBadge({ kind }: { kind: SpanKind }) {
  const { label, tone } = SPAN_KIND[kind];
  return <Badge tone={tone}>{label}</Badge>;
}

export function SeverityBadge({ severity }: { severity: "warning" | "critical" }) {
  const { label, tone } = SEVERITY[severity];
  return <Badge tone={tone}>{label}</Badge>;
}

export function BudgetStateBadge({ state }: { state: Budget["state"] }) {
  const { label, tone } = BUDGET_STATE[state];
  return <Badge tone={tone}>{label}</Badge>;
}
