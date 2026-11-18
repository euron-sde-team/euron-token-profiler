"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

/**
 * A panel that slides in from a side: the mobile navigation drawer, a detail panel, a
 * filter panel. It traps focus and closes on Escape like a dialog. A title is required for
 * assistive technology; `hideTitle` keeps it out of sight when the content has its own.
 */
export function SheetContent({
  className,
  children,
  side = "right",
  title,
  description,
  hideTitle = false,
  showClose = true,
  ...props
}: ComponentProps<typeof DialogPrimitive.Content> & {
  side?: "left" | "right";
  title: ReactNode;
  description?: ReactNode;
  hideTitle?: boolean;
  showClose?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="animate-overlay-in fixed inset-0 z-50 bg-black/40 backdrop-blur-[1px]" />
      <DialogPrimitive.Content
        className={cn(
          "border-border bg-card fixed inset-y-0 z-50 flex h-dvh w-[min(92vw,26rem)] flex-col border-x shadow-md outline-none",
          side === "left" ? "animate-sheet-left left-0" : "animate-sheet-right right-0",
          className,
        )}
        {...props}
      >
        <DialogPrimitive.Title className={hideTitle ? "sr-only" : "px-5 pt-5 text-base font-semibold tracking-tight"}>
          {title}
        </DialogPrimitive.Title>
        <DialogPrimitive.Description
          className={description && !hideTitle ? "text-muted-foreground px-5 pt-1 text-[13px]" : "sr-only"}
        >
          {description ?? title}
        </DialogPrimitive.Description>
        {children}
        {showClose ? (
          <DialogPrimitive.Close
            className="text-muted-foreground hover:bg-muted hover:text-foreground absolute top-4 right-4 rounded-md p-1 transition-colors"
            aria-label="Close"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        ) : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
