"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/input";
import { useProject } from "@/lib/project";
import { useCreatePromptVersion } from "@/lib/queries";

/** Save a new immutable version; `name` is fixed when adding a version to an existing prompt. */
export function NewVersionDialog({
  open,
  onOpenChange,
  name,
  template = "",
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name?: string;
  template?: string;
  onCreated?: (name: string, version: number) => void;
}) {
  const { project } = useProject();
  const create = useCreatePromptVersion({ silent: true });
  const [draftName, setDraftName] = useState("");
  const [text, setText] = useState(template);
  const [labels, setLabels] = useState("");
  const [message, setMessage] = useState("");
  const promptName = name ?? draftName.trim();

  async function submit() {
    try {
      const created = await create.mutateAsync({
        project: project.id,
        name: promptName,
        template: text,
        labels: labels
          .split(/[\s,]+/)
          .map((label) => label.trim())
          .filter(Boolean),
        commit_message: message.trim() || undefined,
      });
      toast.success(`Saved ${promptName} version ${created.version}`);
      onOpenChange(false);
      onCreated?.(promptName, created.version);
      setDraftName("");
      setLabels("");
      setMessage("");
      create.reset();
    } catch {
      // Rendered below.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[min(92vw,40rem)]"
        title={name ? `New version of ${name}` : "New prompt"}
        description="Versions never change once saved. Labels such as production move between versions."
      >
        <div className="space-y-4">
          {name ? null : (
            <Field
              label="Name"
              htmlFor="prompt-name"
              hint="Letters, numbers, dots, dashes and slashes, for example support-triage."
            >
              <Input
                id="prompt-name"
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                autoFocus
              />
            </Field>
          )}
          <Field
            label="Template"
            htmlFor="prompt-template"
            hint="Use {{variable}} placeholders; the SDK fills them in."
          >
            <Textarea
              id="prompt-template"
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="min-h-40 font-mono text-[12.5px]"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Labels" htmlFor="prompt-labels" hint="Optional, separated by spaces: production staging.">
              <Input id="prompt-labels" value={labels} onChange={(event) => setLabels(event.target.value)} />
            </Field>
            <Field label="What changed" htmlFor="prompt-message" hint="Optional.">
              <Input id="prompt-message" value={message} onChange={(event) => setMessage(event.target.value)} />
            </Field>
          </div>
          {create.error ? <ErrorNotice message={create.error.message} /> : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button loading={create.isPending} disabled={!promptName || !text.trim()} onClick={submit}>
            Save version
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
