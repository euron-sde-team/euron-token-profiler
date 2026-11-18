"use client";

import { Search, X } from "lucide-react";
import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";

/** A wrapping row of filters above a list. Put a `SearchField` first, then selects. */
export function FilterBar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

/**
 * A search box with a clear button. Controlled; debounce the value with
 * `useDebouncedValue` before it drives a query. `label` is the accessible name.
 */
export function SearchField({
  value,
  onChange,
  label,
  placeholder,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn("relative min-w-48 flex-1 sm:max-w-xs", className)}>
      <Search className="text-subtle pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden />
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
        placeholder={placeholder ?? label}
        className="pr-8 pl-9 [&::-webkit-search-cancel-button]:hidden"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={`Clear ${label.toLowerCase()}`}
          className="text-subtle hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-0.5 transition-colors"
        >
          <X className="size-4" />
        </button>
      ) : null}
    </div>
  );
}
