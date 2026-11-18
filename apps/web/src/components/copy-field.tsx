"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export function CopyButton({
  value,
  label = "Copy",
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      size="sm"
      variant="secondary"
      className={className}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard blocked (insecure origin or permissions): the text stays selectable.
        }
      }}
    >
      {copied ? <Check /> : <Copy />} {copied ? "Copied" : label}
    </Button>
  );
}

/** A value on one line with a copy button (an id, a URL, a one-time secret). */
export function CopyField({ value, label }: { value: string; label: string }) {
  return (
    <div className="border-border bg-muted/60 flex items-center gap-2 rounded-lg border p-1.5 pl-3">
      <code className="min-w-0 flex-1 truncate font-mono text-[12.5px]" aria-label={label}>
        {value}
      </code>
      <CopyButton value={value} />
    </div>
  );
}

/** A multi-line snippet (SDK, curl, CLI) with a copy button. It scrolls sideways when wide. */
export function CodeBlock({
  code,
  label,
  className,
  wrap = false,
}: {
  code: string;
  label: string;
  className?: string;
  /** Wrap long lines (stored payloads) instead of scrolling sideways (commands and snippets). */
  wrap?: boolean;
}) {
  return (
    <div className={cn("border-border bg-muted/60 relative rounded-lg border", className)}>
      <pre
        className={cn(
          "scroll-quiet p-3 pr-24 font-mono text-[12px] leading-relaxed",
          wrap ? "break-words whitespace-pre-wrap" : "overflow-x-auto",
        )}
        aria-label={label}
        tabIndex={0}
      >
        <code>{code}</code>
      </pre>
      <CopyButton value={code} className="absolute top-2 right-2" />
    </div>
  );
}
