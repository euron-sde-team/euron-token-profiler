"use client";

import { PasswordForm } from "@/components/shell/password-form";
import { Dialog, DialogContent } from "@/components/ui/dialog";

export function PasswordDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Change your password"
        description="Every other browser and device signed in as you is signed out."
      >
        <PasswordForm
          idPrefix="dialog-password"
          onDone={() => onOpenChange(false)}
          onCancel={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
