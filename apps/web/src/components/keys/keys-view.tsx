"use client";

import { KeyRound, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CodeBlock, CopyField } from "@/components/copy-field";
import { RelativeTime } from "@/components/domain/relative-time";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { EmptyState, ErrorNotice, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { PageBody, PageHeader } from "@/components/ui/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProject } from "@/lib/project";
import { useCan, useCreateKey, useKeys, useRevokeKey } from "@/lib/queries";
import { runtimeEnv } from "@/lib/runtime-env";
import { curlSnippet, otlpSnippet, pythonSnippet } from "@/lib/snippets";
import type { ProjectKey, ProjectKeyCreated } from "@/lib/types";

function Connect({ keyValue }: { keyValue: string }) {
  const input = { apiUrl: runtimeEnv().apiUrl, key: keyValue };
  return (
    <Tabs defaultValue="python">
      <TabsList>
        <TabsTrigger value="python">Python SDK</TabsTrigger>
        <TabsTrigger value="otlp">OpenTelemetry</TabsTrigger>
        <TabsTrigger value="curl">curl</TabsTrigger>
      </TabsList>
      <TabsContent value="python">
        <CodeBlock code={pythonSnippet(input)} label="Python SDK example" />
      </TabsContent>
      <TabsContent value="otlp">
        <CodeBlock code={otlpSnippet(input)} label="OpenTelemetry example" />
      </TabsContent>
      <TabsContent value="curl">
        <CodeBlock code={curlSnippet(input)} label="curl example" />
      </TabsContent>
    </Tabs>
  );
}

function CreateKeyDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { project } = useProject();
  const create = useCreateKey({ silent: true });
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ProjectKeyCreated | null>(null);

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setCreated(null);
      setName("");
      create.reset();
    }
  }

  async function submit() {
    try {
      setCreated(await create.mutateAsync({ project: project.id, name: name.trim() }));
    } catch {
      // Rendered below.
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      {created ? (
        <DialogContent
          className="w-[min(92vw,40rem)]"
          title="Key created"
          description="Copy it now. Only a keyed hash is stored, so it cannot be shown again."
        >
          <CopyField value={created.key} label="API key" />
          <p className="text-muted-foreground mt-4 mb-2 text-[13px]">Send your first trace:</p>
          <Connect keyValue={created.key} />
          <DialogFooter>
            <Button onClick={() => close(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      ) : (
        <DialogContent
          title="Create an API key"
          description={`Keys send traces to ${project.name} and fetch its prompts.`}
        >
          <Field label="Name" htmlFor="key-name" hint="What will use it, for example checkout-service.">
            <Input
              id="key-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
              onKeyDown={(event) => {
                if (event.key === "Enter" && name.trim()) void submit();
              }}
            />
          </Field>
          {create.error ? <ErrorNotice message={create.error.message} className="mt-4" /> : null}
          <DialogFooter>
            <Button variant="secondary" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button loading={create.isPending} disabled={!name.trim()} onClick={submit}>
              Create key
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}

export function KeysView() {
  const { project } = useProject();
  const keys = useKeys(project.id);
  const revoke = useRevokeKey();
  const canWrite = useCan("member");
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState<ProjectKey | null>(null);

  return (
    <PageBody>
      <PageHeader
        title="API keys"
        description={`Keys for ${project.name}. SDKs and OpenTelemetry exporters use them to send traces and fetch prompts.`}
        actions={
          canWrite ? (
            <Button onClick={() => setCreating(true)}>
              <Plus /> Create key
            </Button>
          ) : null
        }
      />
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Send traces</CardTitle>
          <CardDescription>Three ways in: the Python SDK, any OpenTelemetry exporter, or plain HTTP.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-3 max-w-md">
            <CopyField value={runtimeEnv().apiUrl} label="API URL" />
          </div>
          <Connect keyValue="tp_your_key_here" />
        </CardContent>
      </Card>

      {keys.error ? (
        <ErrorState message={keys.error.message} onRetry={() => keys.refetch()} />
      ) : !keys.data ? (
        <Skeleton className="h-48" />
      ) : keys.data.items.length === 0 ? (
        <EmptyState
          icon={<KeyRound />}
          title="No API keys yet"
          description="Create one to send traces from an application."
          action={canWrite ? <Button onClick={() => setCreating(true)}>Create key</Button> : undefined}
        />
      ) : (
        <TableContainer label="API keys">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Key</TableHead>
                <TableHead>Created by</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Created</TableHead>
                <TableHead className="text-right">Last used</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.data.items.map((key) => (
                <TableRow key={key.id}>
                  <TableCell>
                    <span className="font-medium">{key.name}</span>
                    <span className="text-muted-foreground block font-mono text-xs">tp_{key.prefix}_...</span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{key.created_by_name ?? "-"}</TableCell>
                  <TableCell>
                    {key.revoked_at ? <Badge>Revoked</Badge> : <Badge tone="success">Active</Badge>}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-right">
                    <RelativeTime iso={key.created_at} />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-right">
                    <RelativeTime iso={key.last_used_at} />
                  </TableCell>
                  <TableCell className="text-right">
                    {canWrite && !key.revoked_at ? (
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label={`Revoke ${key.name}`}
                        onClick={() => setRevoking(key)}
                      >
                        <Trash2 />
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <CreateKeyDialog open={creating} onOpenChange={setCreating} />
      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title="Revoke this key?"
        description={`Anything still using ${revoking?.name ?? "the key"} stops being able to send traces.`}
        confirmLabel="Revoke"
        destructive
        onConfirm={async () => {
          if (revoking) await revoke.mutateAsync({ project: project.id, id: revoking.id });
          toast.success("Key revoked");
        }}
      />
    </PageBody>
  );
}
