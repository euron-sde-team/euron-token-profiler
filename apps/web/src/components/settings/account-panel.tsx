"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { PasswordForm } from "@/components/shell/password-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { ROLE } from "@/lib/labels";
import { useMe, useSystemInfo, useUpdateProfile } from "@/lib/queries";

export function AccountPanel() {
  const me = useMe();
  const system = useSystemInfo();
  const update = useUpdateProfile();
  const [name, setName] = useState<string | null>(null);
  if (!me.data) return null;
  const value = name ?? me.data.name;

  async function save(event: FormEvent) {
    event.preventDefault();
    await update.mutateAsync(value.trim());
    toast.success("Profile saved");
    setName(null);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>
            {me.data.email} <Badge tone="primary">{ROLE[me.data.role].label}</Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="flex max-w-md items-end gap-3">
            <Field label="Display name" htmlFor="profile-name" className="flex-1">
              <Input id="profile-name" value={value} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Button type="submit" loading={update.isPending} disabled={!value.trim() || value.trim() === me.data.name}>
              Save
            </Button>
          </form>
          <p className="text-muted-foreground mt-3 text-[13px]">{ROLE[me.data.role].description}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Changing it signs out every other browser you are signed in on.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-w-md">
            <PasswordForm idPrefix="account-password" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>About this deployment</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid max-w-xl grid-cols-2 gap-x-6 gap-y-2 text-[13px]">
            <dt className="text-muted-foreground">Version</dt>
            <dd>{system.data?.version}</dd>
            <dt className="text-muted-foreground">Archive store</dt>
            <dd>{system.data?.archive_store === "s3" ? "Amazon S3 (SSE-KMS)" : "Local directory"}</dd>
            <dt className="text-muted-foreground">Ingest limit per key</dt>
            <dd>{system.data?.ingest_rate_limit} requests per minute</dd>
            <dt className="text-muted-foreground">Dashboard cache</dt>
            <dd>{system.data?.dashboard_cache_ttl_s} seconds</dd>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
