"use client";

import { AlertDialog as AlertDialogPrimitive } from "radix-ui";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

/**
 * Confirm something that cannot be undone (deleting a memory, erasing a user, deleting a
 * project). The dialog stays open while `onConfirm` runs and closes when it resolves; if it
 * throws, the dialog stays open and the caller shows the error (the mutation hooks toast).
 * `requireText` asks the person to type a word first (the user id, the project slug).
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  requireText,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  requireText?: string;
  onConfirm: () => void | Promise<unknown>;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const [pending, setPending] = useState(false);
  const ready = !requireText || typed.trim() === requireText;

  async function confirm() {
    setPending(true);
    try {
      await onConfirm();
      onOpenChange(false);
      setTyped("");
    } catch {
      // The caller reports the failure; keep the dialog open so nothing is lost.
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!pending) onOpenChange(next);
        if (!next) setTyped("");
      }}
    >
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay className="animate-overlay-in fixed inset-0 z-50 bg-black/40 backdrop-blur-[1px]" />
        <AlertDialogPrimitive.Content className="border-border bg-card data-[state=open]:animate-fade-in fixed top-1/2 left-1/2 z-50 w-[min(92vw,28rem)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border p-5 shadow-md">
          <AlertDialogPrimitive.Title className="text-base font-semibold tracking-tight">
            {title}
          </AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description asChild>
            <div className="text-muted-foreground mt-1.5 text-[13px] leading-relaxed">{description}</div>
          </AlertDialogPrimitive.Description>
          {children ? <div className="mt-3">{children}</div> : null}
          {requireText ? (
            <div className="mt-4 space-y-1.5">
              <Label htmlFor="confirm-text">
                Type <code className="font-mono">{requireText}</code> to confirm
              </Label>
              <Input
                id="confirm-text"
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          ) : null}
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialogPrimitive.Cancel asChild>
              <Button variant="secondary" disabled={pending}>
                {cancelLabel}
              </Button>
            </AlertDialogPrimitive.Cancel>
            <Button variant={destructive ? "danger" : "primary"} loading={pending} disabled={!ready} onClick={confirm}>
              {confirmLabel}
            </Button>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
