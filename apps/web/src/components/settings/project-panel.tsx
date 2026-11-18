"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field, FieldHint, Input, Label, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { DETECTOR_LABEL } from "@/lib/labels";
import { useProject } from "@/lib/project";
import { useCan, useDeleteProject, useTestRedaction, useUpdateProject } from "@/lib/queries";
import type { CustomRule, Project, ProjectUpdate, RedactionRules } from "@/lib/types";

function Section({
  title,
  description,
  children,
  dirty,
  saving,
  canEdit,
  onSave,
}: {
  title: string;
  description: ReactNode;
  children: ReactNode;
  dirty: boolean;
  saving: boolean;
  canEdit: boolean;
  onSave: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
      {canEdit ? (
        <CardFooter>
          <Button loading={saving} disabled={!dirty} onClick={onSave}>
            Save {title.toLowerCase()}
          </Button>
        </CardFooter>
      ) : null}
    </Card>
  );
}

function useSection(project: Project) {
  const update = useUpdateProject();
  async function save(body: ProjectUpdate, done: string) {
    await update.mutateAsync({ id: project.id, ...body });
    toast.success(done);
  }
  return { save, saving: update.isPending };
}

function General({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { save, saving } = useSection(project);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const dirty = name.trim() !== project.name || description !== project.description;
  return (
    <Section
      title="General"
      description={`Slug ${project.slug}. It names the project in archives and webhooks.`}
      dirty={dirty && Boolean(name.trim())}
      saving={saving}
      canEdit={canEdit}
      onSave={() => save({ name: name.trim(), description }, "Project saved")}
    >
      <Field label="Name" htmlFor="project-name">
        <Input id="project-name" value={name} disabled={!canEdit} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="Description" htmlFor="project-description">
        <Input
          id="project-description"
          value={description}
          disabled={!canEdit}
          onChange={(event) => setDescription(event.target.value)}
        />
      </Field>
    </Section>
  );
}

function Sampling({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { save, saving } = useSection(project);
  const initial = String(Math.round(Number(project.sampling_rate) * 1000) / 10);
  const [rate, setRate] = useState(initial);
  const [keepErrors, setKeepErrors] = useState(project.keep_errors);
  const [slow, setSlow] = useState(project.keep_slow_ms ? String(project.keep_slow_ms) : "");
  const valid = rate !== "" && Number(rate) >= 0 && Number(rate) <= 100;
  const dirty =
    rate !== initial ||
    keepErrors !== project.keep_errors ||
    slow !== (project.keep_slow_ms ? String(project.keep_slow_ms) : "");
  return (
    <Section
      title="Sampling"
      description="Keep a share of traces to control volume. The choice is made per trace id, so a kept trace is always complete."
      dirty={dirty && valid}
      saving={saving}
      canEdit={canEdit}
      onSave={() =>
        save(
          {
            sampling_rate: Number(rate) / 100,
            keep_errors: keepErrors,
            ...(slow ? { keep_slow_ms: Number(slow) } : { clear_keep_slow: true }),
          },
          "Sampling saved",
        )
      }
    >
      <Field label="Share of traces kept, %" htmlFor="sampling-rate" hint="100 keeps everything.">
        <Input
          id="sampling-rate"
          type="number"
          min={0}
          max={100}
          step={0.1}
          value={rate}
          disabled={!canEdit}
          onChange={(event) => setRate(event.target.value)}
          className="max-w-40"
        />
      </Field>
      <div className="flex items-center justify-between gap-4">
        <div>
          <Label htmlFor="keep-errors">Always keep failing traces</Label>
          <FieldHint>A trace with an error span is stored even when sampling would drop it.</FieldHint>
        </div>
        <Switch id="keep-errors" checked={keepErrors} disabled={!canEdit} onCheckedChange={setKeepErrors} />
      </div>
      <Field label="Always keep spans slower than, ms" htmlFor="keep-slow" hint="Blank turns this off.">
        <Input
          id="keep-slow"
          type="number"
          min={1}
          value={slow}
          disabled={!canEdit}
          onChange={(event) => setSlow(event.target.value)}
          className="max-w-40"
        />
      </Field>
    </Section>
  );
}

function Privacy({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { save, saving } = useSection(project);
  const test = useTestRedaction();
  const [rules, setRules] = useState<RedactionRules>(project.redaction);
  const [sample, setSample] = useState("Write to sam.lee@example.com or call +1 415-555-0134.");
  const dirty = JSON.stringify(rules) !== JSON.stringify(project.redaction);
  const customOk = rules.custom.every((rule) => rule.name.trim() && rule.pattern.trim());

  const setRule = (index: number, patch: Partial<CustomRule>) =>
    setRules({ ...rules, custom: rules.custom.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)) });

  return (
    <Section
      title="Privacy"
      description="Masking runs before anything is written, so removed values never reach the database. Numbers and keys are left alone."
      dirty={dirty && customOk}
      saving={saving}
      canEdit={canEdit}
      onSave={() => save({ redaction: rules }, "Privacy rules saved")}
    >
      <fieldset className="grid gap-2 sm:grid-cols-2" disabled={!canEdit}>
        <legend className="text-foreground mb-1.5 text-[13px] font-medium">Built-in detectors</legend>
        {Object.entries(DETECTOR_LABEL).map(([id, label]) => (
          <label key={id} className="flex items-center gap-2 text-[13px]">
            <Checkbox
              checked={rules.detectors.includes(id)}
              onCheckedChange={(checked) =>
                setRules({
                  ...rules,
                  detectors: checked ? [...rules.detectors, id] : rules.detectors.filter((d) => d !== id),
                })
              }
            />
            {label}
          </label>
        ))}
      </fieldset>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-medium">Custom patterns</p>
          {canEdit ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                setRules({ ...rules, custom: [...rules.custom, { name: "", pattern: "", replacement: "[REDACTED]" }] })
              }
            >
              <Plus /> Add pattern
            </Button>
          ) : null}
        </div>
        {rules.custom.length === 0 ? (
          <FieldHint>Regular expressions for what only you know, such as employee ids.</FieldHint>
        ) : (
          rules.custom.map((rule, index) => (
            <div key={index} className="grid items-end gap-2 sm:grid-cols-[1fr_2fr_1fr_auto]">
              <Field label="Name" htmlFor={`rule-name-${index}`}>
                <Input
                  id={`rule-name-${index}`}
                  value={rule.name}
                  disabled={!canEdit}
                  onChange={(e) => setRule(index, { name: e.target.value })}
                />
              </Field>
              <Field label="Pattern" htmlFor={`rule-pattern-${index}`}>
                <Input
                  id={`rule-pattern-${index}`}
                  className="font-mono text-[12.5px]"
                  value={rule.pattern}
                  disabled={!canEdit}
                  onChange={(e) => setRule(index, { pattern: e.target.value })}
                />
              </Field>
              <Field label="Replacement" htmlFor={`rule-replacement-${index}`}>
                <Input
                  id={`rule-replacement-${index}`}
                  value={rule.replacement}
                  disabled={!canEdit}
                  onChange={(e) => setRule(index, { replacement: e.target.value })}
                />
              </Field>
              {canEdit ? (
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove pattern ${rule.name || index + 1}`}
                  onClick={() => setRules({ ...rules, custom: rules.custom.filter((_, i) => i !== index) })}
                >
                  <Trash2 />
                </Button>
              ) : null}
            </div>
          ))
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="store-payloads">Store inputs and outputs</Label>
            <FieldHint>Off keeps only the shape, usage and cost.</FieldHint>
          </div>
          <Switch
            id="store-payloads"
            checked={rules.store_payloads}
            disabled={!canEdit}
            onCheckedChange={(checked) => setRules({ ...rules, store_payloads: checked })}
          />
        </div>
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="redact-metadata">Mask metadata too</Label>
            <FieldHint>Applies the same rules to span metadata.</FieldHint>
          </div>
          <Switch
            id="redact-metadata"
            checked={rules.redact_metadata}
            disabled={!canEdit}
            onCheckedChange={(checked) => setRules({ ...rules, redact_metadata: checked })}
          />
        </div>
      </div>
      <Field label="Longest stored payload, characters" htmlFor="max-chars" hint="Longer inputs and outputs are cut.">
        <Input
          id="max-chars"
          type="number"
          min={100}
          max={200000}
          value={rules.max_payload_chars}
          disabled={!canEdit}
          onChange={(event) => setRules({ ...rules, max_payload_chars: Number(event.target.value) || 100 })}
          className="max-w-40"
        />
      </Field>

      <div className="border-border rounded-lg border p-3">
        <Field label="Try the rules on a sample" htmlFor="redaction-sample" hint="Uses the rules above, saved or not.">
          <Textarea
            id="redaction-sample"
            value={sample}
            onChange={(event) => setSample(event.target.value)}
            className="min-h-16"
          />
        </Field>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant="secondary"
            loading={test.isPending}
            disabled={!sample.trim() || !customOk}
            onClick={() => test.mutate({ project: project.id, text: sample, redaction: rules })}
          >
            Test masking
          </Button>
          {test.data ? (
            <span className="text-[13px]" role="status">
              <Badge tone="info">{test.data.redactions} masked</Badge>{" "}
              <code className="font-mono text-[12.5px]">{test.data.redacted}</code>
            </span>
          ) : null}
          {test.error ? <span className="text-danger text-[13px]">{test.error.message}</span> : null}
        </div>
      </div>
    </Section>
  );
}

function Retention({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { save, saving } = useSection(project);
  const [days, setDays] = useState(String(project.retention_days));
  const [archive, setArchive] = useState(project.archive_before_delete);
  const valid = Number(days) >= 1 && Number(days) <= 3650;
  return (
    <Section
      title="Retention"
      description="Older traces are deleted in small batches. With archiving on, each batch is written to the archive store first and kept if that fails."
      dirty={(days !== String(project.retention_days) || archive !== project.archive_before_delete) && valid}
      saving={saving}
      canEdit={canEdit}
      onSave={() => save({ retention_days: Number(days), archive_before_delete: archive }, "Retention saved")}
    >
      <Field label="Keep traces for, days" htmlFor="retention-days">
        <Input
          id="retention-days"
          type="number"
          min={1}
          max={3650}
          value={days}
          disabled={!canEdit}
          onChange={(event) => setDays(event.target.value)}
          className="max-w-40"
        />
      </Field>
      <div className="flex items-center justify-between gap-4">
        <div>
          <Label htmlFor="archive-before-delete">Archive before delete</Label>
          <FieldHint>Gzip NDJSON, one object per batch, in S3 with SSE-KMS or on a volume.</FieldHint>
        </div>
        <Switch id="archive-before-delete" checked={archive} disabled={!canEdit} onCheckedChange={setArchive} />
      </div>
    </Section>
  );
}

function Notifications({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { save, saving } = useSection(project);
  const [url, setUrl] = useState("");
  return (
    <Section
      title="Notifications"
      description="Budgets and alert rules POST JSON here when they fire, escalate and resolve. The URL is stored encrypted and only public addresses are accepted."
      dirty={url.trim() !== ""}
      saving={saving}
      canEdit={canEdit}
      onSave={async () => {
        await save({ webhook_url: url.trim() }, "Webhook saved");
        setUrl("");
      }}
    >
      <Field
        label="Webhook URL"
        htmlFor="webhook-url"
        hint={project.has_webhook ? "A webhook is set. Enter a new URL to replace it." : "No webhook is set."}
      >
        <Input
          id="webhook-url"
          type="url"
          placeholder={project.has_webhook ? "https://hooks.example.com/..." : "https://"}
          value={url}
          disabled={!canEdit}
          onChange={(event) => setUrl(event.target.value)}
        />
      </Field>
      {canEdit && project.has_webhook ? (
        <Button variant="secondary" size="sm" onClick={() => save({ webhook_url: "" }, "Webhook removed")}>
          Remove webhook
        </Button>
      ) : null}
    </Section>
  );
}

function DangerZone({ project }: { project: Project }) {
  const remove = useDeleteProject();
  const { projects, select } = useProject();
  const [open, setOpen] = useState(false);
  return (
    <Card className="border-danger/30">
      <CardHeader>
        <CardTitle>Delete project</CardTitle>
        <CardDescription>
          Removes every trace, prompt, price override, budget and key of {project.name}. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button variant="danger" disabled={projects.length <= 1} onClick={() => setOpen(true)}>
          Delete {project.name}
        </Button>
        {projects.length <= 1 ? (
          <span className="text-muted-foreground mr-auto text-xs">Keep at least one project.</span>
        ) : null}
      </CardFooter>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={`Delete ${project.name}?`}
        description="All of its data is deleted at once."
        confirmLabel="Delete project"
        destructive
        requireText={project.slug}
        onConfirm={async () => {
          await remove.mutateAsync(project.id);
          const other = projects.find((p) => p.id !== project.id);
          if (other) select(other.id);
          toast.success("Project deleted");
        }}
      />
    </Card>
  );
}

export function ProjectPanel() {
  const { project } = useProject();
  const admin = useCan("admin");
  // Re-mount the sections when another project is chosen, so their drafts reset.
  return (
    <div className="space-y-6" key={project.id}>
      {admin ? null : (
        <p className="text-muted-foreground text-[13px]">Only administrators can change project settings.</p>
      )}
      <General project={project} canEdit={admin} />
      <Sampling project={project} canEdit={admin} />
      <Privacy project={project} canEdit={admin} />
      <Retention project={project} canEdit={admin} />
      <Notifications project={project} canEdit={admin} />
      {admin ? <DangerZone project={project} /> : null}
    </div>
  );
}
