"use client";

import { Bell, Pencil, Plus, Trash2, Wallet } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BudgetStateBadge, SeverityBadge } from "@/components/domain/badges";
import { RelativeTime } from "@/components/domain/relative-time";
import { BudgetDialog } from "@/components/budgets/budget-dialog";
import { RuleDialog } from "@/components/budgets/rule-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Pagination } from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/cn";
import { formatDate, formatUsd } from "@/lib/format";
import { BUDGET_PERIOD, BUDGET_SCOPE, RULE_METRIC } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useAlertEvents, useAlerts, useCan, useDeleteBudget, useDeleteRule } from "@/lib/queries";
import type { AlertEvent, AlertRule, Budget } from "@/lib/types";

const BAR = { ok: "bg-success", warning: "bg-warning", exceeded: "bg-danger" } as const;

function describeRule(rule: AlertRule): string {
  const info = RULE_METRIC[rule.metric];
  const value = Number(rule.threshold);
  const shown =
    info.unit === "USD"
      ? `$${value}`
      : info.unit === "%"
        ? `${value}%`
        : info.unit === "ms"
          ? `${value} ms`
          : String(value);
  return `${info.label} ${rule.comparator} ${shown} over ${rule.window_minutes} min`;
}

function eventValue(event: AlertEvent): string {
  if (event.kind === "budget") return `${formatUsd(event.value)} of ${formatUsd(event.threshold)}`;
  return `${Number(event.value)} vs ${Number(event.threshold)}`;
}

function BudgetCard({
  budget,
  canWrite,
  onEdit,
  onDelete,
}: {
  budget: Budget;
  canWrite: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[14px] font-semibold break-words">{budget.name}</p>
            <p className="text-muted-foreground text-xs">
              {BUDGET_PERIOD[budget.period]},{" "}
              {budget.scope === "project" ? BUDGET_SCOPE.project.toLowerCase() : budget.scope_value}
            </p>
          </div>
          <BudgetStateBadge state={budget.state} />
        </div>
        <div>
          <div className="flex items-baseline justify-between text-[13px]">
            <span className="tabular text-[20px] font-semibold">{formatUsd(budget.spent_usd)}</span>
            <span className="text-muted-foreground tabular">of {formatUsd(budget.limit_usd)}</span>
          </div>
          <div
            role="progressbar"
            aria-label={`${budget.name} used`}
            aria-valuenow={Math.min(100, Math.round(budget.percent_used))}
            aria-valuemin={0}
            aria-valuemax={100}
            className="bg-muted relative mt-2 h-2 rounded-full"
          >
            <div
              className={cn("h-2 rounded-full", BAR[budget.state])}
              style={{ width: `${Math.min(100, budget.percent_used)}%` }}
            />
            <span
              className="bg-foreground/40 absolute top-[-2px] h-3 w-px"
              style={{ left: `${budget.warn_at_percent}%` }}
              aria-hidden
            />
          </div>
          <p className="text-muted-foreground mt-1.5 text-xs">
            {budget.percent_used.toFixed(0)}% used, resets {formatDate(budget.period_end)}. Warns at{" "}
            {budget.warn_at_percent}%.
          </p>
        </div>
        {canWrite ? (
          <div className="flex justify-end gap-1">
            <Button size="icon-sm" variant="ghost" aria-label={`Edit ${budget.name}`} onClick={onEdit}>
              <Pencil />
            </Button>
            <Button size="icon-sm" variant="ghost" aria-label={`Delete ${budget.name}`} onClick={onDelete}>
              <Trash2 />
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function BudgetsView() {
  const { project } = useProject();
  const alerts = useAlerts(project.id);
  const [offset, setOffset] = useState(0);
  const events = useAlertEvents(project.id, { limit: 10, offset });
  const canWrite = useCan("member");
  const removeBudget = useDeleteBudget();
  const removeRule = useDeleteRule();
  const [budget, setBudget] = useState<Budget | "new" | null>(null);
  const [rule, setRule] = useState<AlertRule | "new" | null>(null);
  const [deletingBudget, setDeletingBudget] = useState<Budget | null>(null);
  const [deletingRule, setDeletingRule] = useState<AlertRule | null>(null);

  return (
    <PageBody className="max-w-7xl">
      <PageHeader
        title="Budgets and alerts"
        description="Spend limits per period and health checks over your traces. Notifications go to the project webhook."
        actions={
          canWrite ? (
            <>
              <Button variant="secondary" onClick={() => setRule("new")}>
                <Plus /> New rule
              </Button>
              <Button onClick={() => setBudget("new")}>
                <Plus /> New budget
              </Button>
            </>
          ) : null
        }
      />
      {alerts.error ? (
        <ErrorState message={alerts.error.message} onRetry={() => alerts.refetch()} />
      ) : !alerts.data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="space-y-8">
          <section aria-labelledby="budgets-title">
            <h2 id="budgets-title" className="mb-3 text-[15px] font-semibold tracking-tight">
              Budgets
            </h2>
            {alerts.data.budgets.length === 0 ? (
              <EmptyState
                icon={<Wallet />}
                title="No budgets"
                description="Set a limit and be told before the bill arrives."
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {alerts.data.budgets.map((item) => (
                  <BudgetCard
                    key={item.id}
                    budget={item}
                    canWrite={canWrite}
                    onEdit={() => setBudget(item)}
                    onDelete={() => setDeletingBudget(item)}
                  />
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="rules-title">
            <h2 id="rules-title" className="mb-3 text-[15px] font-semibold tracking-tight">
              Alert rules
            </h2>
            {alerts.data.rules.length === 0 ? (
              <EmptyState
                icon={<Bell />}
                title="No alert rules"
                description="Alert on error rate, latency, spend or silence."
              />
            ) : (
              <TableContainer label="Alert rules">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rule</TableHead>
                      <TableHead>Condition</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {alerts.data.rules.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="text-muted-foreground">{describeRule(item)}</TableCell>
                        <TableCell>
                          <SeverityBadge severity={item.severity} />
                        </TableCell>
                        <TableCell>
                          {!item.enabled ? (
                            <Badge>Disabled</Badge>
                          ) : item.firing ? (
                            <Badge tone="danger">Firing</Badge>
                          ) : (
                            <Badge tone="success">Healthy</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {canWrite ? (
                            <span className="inline-flex gap-1">
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                aria-label={`Edit ${item.name}`}
                                onClick={() => setRule(item)}
                              >
                                <Pencil />
                              </Button>
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                aria-label={`Delete ${item.name}`}
                                onClick={() => setDeletingRule(item)}
                              >
                                <Trash2 />
                              </Button>
                            </span>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </section>

          <section aria-labelledby="history-title">
            <h2 id="history-title" className="mb-3 text-[15px] font-semibold tracking-tight">
              History
            </h2>
            {!events.data || events.data.items.length === 0 ? (
              <p className="text-muted-foreground text-[13px]">Nothing has fired yet.</p>
            ) : (
              <>
                <TableContainer label="Alert history">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Alert</TableHead>
                        <TableHead>State</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>Value</TableHead>
                        <TableHead className="text-right">Fired</TableHead>
                        <TableHead className="text-right">Resolved</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {events.data.items.map((event) => (
                        <TableRow key={event.id}>
                          <TableCell className="max-w-96">
                            <span className="font-medium">{event.source_name}</span>
                            <span className="text-muted-foreground block truncate text-xs" title={event.message}>
                              {event.message}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge tone={event.state === "firing" ? "danger" : "success"}>
                              {event.state === "firing" ? "Firing" : "Resolved"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <SeverityBadge severity={event.severity} />
                          </TableCell>
                          <TableCell className="tabular text-muted-foreground">{eventValue(event)}</TableCell>
                          <TableCell className="text-muted-foreground text-right">
                            <RelativeTime iso={event.fired_at} />
                          </TableCell>
                          <TableCell className="text-muted-foreground text-right">
                            <RelativeTime iso={event.resolved_at} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <Pagination
                  className="mt-4"
                  total={events.data.total}
                  limit={10}
                  offset={offset}
                  onOffsetChange={setOffset}
                  noun="alerts"
                />
              </>
            )}
          </section>
        </div>
      )}
      {budget ? (
        <BudgetDialog
          key={budget === "new" ? "new" : budget.id}
          budget={budget}
          onOpenChange={(open) => !open && setBudget(null)}
        />
      ) : null}
      {rule ? (
        <RuleDialog
          key={rule === "new" ? "new" : rule.id}
          rule={rule}
          onOpenChange={(open) => !open && setRule(null)}
        />
      ) : null}
      <ConfirmDialog
        open={deletingBudget !== null}
        onOpenChange={(open) => !open && setDeletingBudget(null)}
        title="Delete this budget?"
        description={`${deletingBudget?.name ?? "The budget"} and its alert history are removed.`}
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (deletingBudget) await removeBudget.mutateAsync({ project: project.id, id: deletingBudget.id });
          toast.success("Budget deleted");
        }}
      />
      <ConfirmDialog
        open={deletingRule !== null}
        onOpenChange={(open) => !open && setDeletingRule(null)}
        title="Delete this rule?"
        description={`${deletingRule?.name ?? "The rule"} and its alert history are removed.`}
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (deletingRule) await removeRule.mutateAsync({ project: project.id, id: deletingRule.id });
          toast.success("Rule deleted");
        }}
      />
    </PageBody>
  );
}
