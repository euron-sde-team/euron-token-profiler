"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice } from "@/components/ui/feedback";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { RULE_METRIC } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useSaveRule } from "@/lib/queries";
import type { AlertRule, RuleMetric } from "@/lib/types";

export function RuleDialog({ rule, onOpenChange }: { rule: AlertRule | "new"; onOpenChange: (open: boolean) => void }) {
  const existing = rule === "new" ? null : rule;
  const { project } = useProject();
  const save = useSaveRule({ silent: true });
  const [name, setName] = useState(existing?.name ?? "");
  const [metric, setMetric] = useState<RuleMetric>(existing?.metric ?? "error_rate");
  const [comparator, setComparator] = useState(existing?.comparator ?? "above");
  const [threshold, setThreshold] = useState(existing ? String(Number(existing.threshold)) : "");
  const [window, setWindow] = useState(String(existing?.window_minutes ?? 60));
  const [minTraces, setMinTraces] = useState(String(existing?.min_traces ?? 10));
  const [severity, setSeverity] = useState(existing?.severity ?? "warning");

  async function submit() {
    try {
      await save.mutateAsync({
        project: project.id,
        id: existing?.id,
        body: {
          name: name.trim(),
          metric,
          comparator,
          threshold,
          window_minutes: Number(window),
          min_traces: Number(minTraces),
          severity,
          enabled: existing?.enabled ?? true,
        },
      });
      toast.success(existing ? "Rule updated" : "Rule created");
      onOpenChange(false);
    } catch {
      // Rendered below.
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        title={existing ? "Edit alert rule" : "New alert rule"}
        description="Checked every 30 seconds over a trailing window. The alert resolves on its own when the metric recovers."
      >
        <div className="space-y-4">
          <Field label="Name" htmlFor="rule-name">
            <Input id="rule-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Metric" htmlFor="rule-metric">
              <NativeSelect
                id="rule-metric"
                value={metric}
                onChange={(event) => setMetric(event.target.value as RuleMetric)}
              >
                {Object.entries(RULE_METRIC).map(([key, info]) => (
                  <option key={key} value={key}>
                    {info.label}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Fires when" htmlFor="rule-comparator">
              <NativeSelect
                id="rule-comparator"
                value={comparator}
                onChange={(event) => setComparator(event.target.value as "above" | "below")}
              >
                <option value="above">Above</option>
                <option value="below">Below</option>
              </NativeSelect>
            </Field>
            <Field label={`Threshold (${RULE_METRIC[metric].unit})`} htmlFor="rule-threshold">
              <Input
                id="rule-threshold"
                inputMode="decimal"
                value={threshold}
                onChange={(event) => setThreshold(event.target.value)}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Window, minutes" htmlFor="rule-window">
              <Input
                id="rule-window"
                type="number"
                min={1}
                max={10080}
                value={window}
                onChange={(event) => setWindow(event.target.value)}
              />
            </Field>
            <Field label="Minimum traces" htmlFor="rule-min" hint="Fewer is treated as no data.">
              <Input
                id="rule-min"
                type="number"
                min={0}
                value={minTraces}
                onChange={(event) => setMinTraces(event.target.value)}
              />
            </Field>
            <Field label="Severity" htmlFor="rule-severity">
              <NativeSelect
                id="rule-severity"
                value={severity}
                onChange={(event) => setSeverity(event.target.value as "warning" | "critical")}
              >
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </NativeSelect>
            </Field>
          </div>
          {save.error ? <ErrorNotice message={save.error.message} /> : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button loading={save.isPending} disabled={!name.trim() || threshold === ""} onClick={submit}>
            {existing ? "Save rule" : "Create rule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
