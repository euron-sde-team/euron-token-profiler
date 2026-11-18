"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice, ErrorState, Skeleton } from "@/components/ui/feedback";
import { SearchField } from "@/components/ui/filter-bar";
import { Field, Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProject } from "@/lib/project";
import { useCan, useDeletePrice, usePrices, useUpsertPrice } from "@/lib/queries";
import type { Price } from "@/lib/types";

const money = (value: string | null) => (value === null ? "-" : `$${Number(value)}`);

function OverrideDialog({
  open,
  onOpenChange,
  price,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  price: Price | null;
}) {
  const { project } = useProject();
  const save = useUpsertPrice({ silent: true });
  const [model, setModel] = useState(price?.model ?? "");
  const [input, setInput] = useState(price ? String(Number(price.input_per_mtok)) : "");
  const [output, setOutput] = useState(price ? String(Number(price.output_per_mtok)) : "");
  const [cached, setCached] = useState(price?.cached_input_per_mtok ? String(Number(price.cached_input_per_mtok)) : "");

  async function submit() {
    try {
      await save.mutateAsync({
        project: project.id,
        model: model.trim(),
        provider: price?.provider ?? "",
        input_per_mtok: input,
        output_per_mtok: output,
        cached_input_per_mtok: cached || null,
      });
      toast.success(`Override saved for ${model.trim()}`);
      onOpenChange(false);
    } catch {
      // Rendered below.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={
          price?.scope === "shared" ? `Override ${price.model}` : price ? `Edit ${price.model}` : "Add a price override"
        }
        description="Applies to this project from now on. Spans already stored keep the price they were billed at."
      >
        <div className="space-y-4">
          <Field
            label="Model name"
            htmlFor="price-model"
            hint="Matched against the model name on spans, ignoring provider prefixes."
          >
            <Input
              id="price-model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              disabled={Boolean(price)}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Input, USD per 1M" htmlFor="price-in">
              <Input
                id="price-in"
                inputMode="decimal"
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
            </Field>
            <Field label="Output, USD per 1M" htmlFor="price-out">
              <Input
                id="price-out"
                inputMode="decimal"
                value={output}
                onChange={(event) => setOutput(event.target.value)}
              />
            </Field>
            <Field label="Cached input" htmlFor="price-cached" hint="Optional.">
              <Input
                id="price-cached"
                inputMode="decimal"
                value={cached}
                onChange={(event) => setCached(event.target.value)}
              />
            </Field>
          </div>
          {save.error ? <ErrorNotice message={save.error.message} /> : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button loading={save.isPending} disabled={!model.trim() || !input || !output} onClick={submit}>
            Save override
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PriceTable() {
  const { project } = useProject();
  const prices = usePrices(project.id);
  const remove = useDeletePrice();
  const canWrite = useCan("member");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Price | "new" | null>(null);
  const [removing, setRemoving] = useState<Price | null>(null);

  if (prices.error) return <ErrorState message={prices.error.message} onRetry={() => prices.refetch()} />;
  if (!prices.data) return <Skeleton className="h-80" />;
  const rows = prices.data.filter((p) => !p.overridden && p.model.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SearchField value={search} onChange={setSearch} label="Search models" />
        {canWrite ? (
          <Button variant="secondary" onClick={() => setEditing("new")}>
            <Plus /> Add override
          </Button>
        ) : null}
      </div>
      <p className="text-muted-foreground mb-3 text-[13px]">
        List prices in USD per million tokens, refreshed with each release. A project override beats the shared row.
        Spans for a model with no price are stored with zero cost and flagged.
      </p>
      <TableContainer label="Model prices">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead className="text-right">Input</TableHead>
              <TableHead className="text-right">Cached input</TableHead>
              <TableHead className="text-right">Output</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((price) => (
              <TableRow key={price.id}>
                <TableCell className="font-medium">{price.model}</TableCell>
                <TableCell className="text-muted-foreground">{price.provider || "-"}</TableCell>
                <TableCell className="tabular text-right">{money(price.input_per_mtok)}</TableCell>
                <TableCell className="tabular text-right">{money(price.cached_input_per_mtok)}</TableCell>
                <TableCell className="tabular text-right">{money(price.output_per_mtok)}</TableCell>
                <TableCell>
                  {price.scope === "project" ? <Badge tone="primary">This project</Badge> : <Badge>Shared</Badge>}
                </TableCell>
                <TableCell className="text-right">
                  {canWrite ? (
                    <span className="inline-flex gap-1">
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label={`${price.scope === "shared" ? "Override" : "Edit"} ${price.model}`}
                        onClick={() => setEditing(price)}
                      >
                        <Pencil />
                      </Button>
                      {price.scope === "project" ? (
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={`Remove override for ${price.model}`}
                          onClick={() => setRemoving(price)}
                        >
                          <Trash2 />
                        </Button>
                      ) : null}
                    </span>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {editing ? (
        <OverrideDialog
          key={editing === "new" ? "new" : editing.id}
          open
          onOpenChange={(open) => !open && setEditing(null)}
          price={editing === "new" ? null : editing}
        />
      ) : null}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title="Remove this override?"
        description={`${removing?.model ?? "The model"} goes back to the shared price for new spans.`}
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          if (removing) await remove.mutateAsync({ project: project.id, id: removing.id });
          toast.success("Override removed");
        }}
      />
    </div>
  );
}
