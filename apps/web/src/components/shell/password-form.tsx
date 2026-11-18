"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { useChangePassword } from "@/lib/queries";

// Mirrors the API's rule (core/security.py validate_password); the API remains the authority.
export const MIN_PASSWORD_LENGTH = 10;

/** Change the signed-in person's password; every other session of theirs is signed out. */
export function PasswordForm({
  onDone,
  onCancel,
  idPrefix = "password",
}: {
  onDone?: () => void;
  onCancel?: () => void;
  idPrefix?: string;
}) {
  const change = useChangePassword({ silent: true });
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && next !== confirm;

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await change.mutateAsync({ current_password: current, new_password: next });
    } catch {
      return; // Rendered from the mutation state below.
    }
    toast.success("Password changed. Your other sessions were signed out.");
    setCurrent("");
    setNext("");
    setConfirm("");
    onDone?.();
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Current password" htmlFor={`${idPrefix}-current`}>
        <Input
          id={`${idPrefix}-current`}
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
          required
        />
      </Field>
      <Field label="New password" htmlFor={`${idPrefix}-new`} hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}>
        <Input
          id={`${idPrefix}-new`}
          type="password"
          autoComplete="new-password"
          value={next}
          minLength={MIN_PASSWORD_LENGTH}
          onChange={(event) => setNext(event.target.value)}
          required
        />
      </Field>
      <Field
        label="Confirm the new password"
        htmlFor={`${idPrefix}-confirm`}
        error={mismatch ? "The passwords do not match." : undefined}
      >
        <Input
          id={`${idPrefix}-confirm`}
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          aria-invalid={mismatch || undefined}
          required
        />
      </Field>
      {change.error ? <ErrorNotice message={change.error.message} /> : null}
      <div className={cn("flex gap-2", onCancel ? "justify-end" : "justify-start")}>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button
          type="submit"
          loading={change.isPending}
          disabled={!current || next.length < MIN_PASSWORD_LENGTH || next !== confirm}
        >
          Change password
        </Button>
      </div>
    </form>
  );
}
