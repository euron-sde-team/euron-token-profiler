"use client";

import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type SegmentOption<T extends string> = { value: T; label: ReactNode; ariaLabel?: string };

/**
 * A row of mutually exclusive choices that looks like one control (a view switch, a time
 * range, a theme). Exactly one option is always selected; `label` names the group.
 */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
  size = "md",
  className,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: readonly SegmentOption<T>[];
  label: string;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <ToggleGroupPrimitive.Root
      type="single"
      value={value}
      // Radix reports "" when the selected item is pressed again; keep the selection.
      onValueChange={(next) => next && onValueChange(next as T)}
      aria-label={label}
      className={cn(
        "bg-muted ring-border inline-flex items-center gap-0.5 rounded-lg p-0.5 ring-1 ring-inset",
        className,
      )}
    >
      {options.map((option) => (
        <ToggleGroupPrimitive.Item
          key={option.value}
          value={option.value}
          aria-label={option.ariaLabel}
          className={cn(
            "text-muted-foreground hover:text-foreground data-[state=on]:bg-card data-[state=on]:text-foreground inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors data-[state=on]:shadow-sm [&_svg]:size-3.5",
            size === "sm" ? "h-6 px-2 text-xs" : "h-7 px-3 text-[13px]",
          )}
        >
          {option.label}
        </ToggleGroupPrimitive.Item>
      ))}
    </ToggleGroupPrimitive.Root>
  );
}
