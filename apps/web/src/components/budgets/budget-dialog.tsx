"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice } from "@/components/ui/feedback";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { BUDGET_PERIOD, BUDGET_SCOPE } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useFacets, useSaveBudget } from "@/lib/queries";
import type { Budget, BudgetPeriod, BudgetScope } from "@/lib/types";

export function BudgetDialog({
  budget,
  onOpenChange,
}: {
  budget: Budget | "new";
  onOpenChange: (open: boolean) => void;
}) {
  const existing = budget === "new" ? null : budget;
  const { project } = useProject();
  const facets = useFacets(project.id);
  const save = useSaveBudget({ silent: true });
  const [name, setName] = useState(existing?.name ?? "");
  const [scope, setScope] = useState<BudgetScope>(existing?.scope ?? "project");
  const [value, setValue] = useState(existing?.scope_value ?? "");
  const [period, setPeriod] = useState<BudgetPeriod>(existing?.period ?? "month");
  const [limit, setLimit] = useState(existing ? String(Number(existing.limit_usd)) : "");
  const [warn, setWarn] = useState(String(existing?.warn_at_percent ?? 80));
  const options =
    scope === "model"
      ? facets.data?.models
      : scope === "agent"
        ? facets.data?.agents
        : scope === "tool"
          ? facets.data?.tools
          : scope === "prompt"
            ? facets.data?.prompts
            : [];

  async function submit() {
    try {
      await save.mutateAsync({
        project: project.id,
        id: existing?.id,
        body: {
          name: name.trim(),
          scope,
          scope_value: scope === "project" ? null : value.trim(),
          period,
          limit_usd: limit,
          warn_at_percent: Number(warn),
          enabled: existing?.enabled ?? true,
        },
      });
      toast.success(existing ? "Budget updated" : "Budget created");
      onOpenChange(false);
    } catch {
      // Rendered below.
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        title={existing ? "Edit budget" : "New budget"}
        description="Spend is counted in UTC calendar periods. You are alerted at the warning level and again at the limit."
      >
        <div className="space-y-4">
          <Field label="Name" htmlFor="budget-name">
            <Input id="budget-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Applies to" htmlFor="budget-scope">
              <NativeSelect
                id="budget-scope"
                value={scope}
                onChange={(event) => {
                  setScope(event.target.value as BudgetScope);
                  setValue("");
                }}
              >
                {Object.entries(BUDGET_SCOPE).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            {scope === "project" ? null : (
              <Field
                label={BUDGET_SCOPE[scope].replace("One ", "").replace(/^./, (c) => c.toUpperCase())}
                htmlFor="budget-value"
              >
                <NativeSelect id="budget-value" value={value} onChange={(event) => setValue(event.target.value)}>
                  <option value="">Choose...</option>
                  {(options ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Period" htmlFor="budget-period">
              <NativeSelect
                id="budget-period"
                value={period}
                onChange={(event) => setPeriod(event.target.value as BudgetPeriod)}
              >
                {Object.entries(BUDGET_PERIOD).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Limit, USD" htmlFor="budget-limit">
              <Input
                id="budget-limit"
                inputMode="decimal"
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
              />
            </Field>
            <Field label="Warn at, %" htmlFor="budget-warn">
              <Input
                id="budget-warn"
                type="number"
                min={1}
                max={100}
                value={warn}
                onChange={(event) => setWarn(event.target.value)}
              />
            </Field>
          </div>
          {save.error ? <ErrorNotice message={save.error.message} /> : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            loading={save.isPending}
            disabled={!name.trim() || !limit || (scope !== "project" && !value)}
            onClick={submit}
          >
            {existing ? "Save budget" : "Create budget"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
