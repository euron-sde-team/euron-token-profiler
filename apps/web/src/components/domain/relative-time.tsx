"use client";

import { formatAge, formatDateTime, formatRelative } from "@/lib/format";

/**
 * "3 days ago" (or "3d" when `compact`), with the exact date and time in the tooltip.
 * Renders a semantic `<time>`. Meant for data loaded in the browser.
 */
export function RelativeTime({
  iso,
  compact = false,
  className,
}: {
  iso: string | null | undefined;
  compact?: boolean;
  className?: string;
}) {
  if (!iso) return <span className={className}>never</span>;
  return (
    <time dateTime={iso} title={formatDateTime(iso)} className={className} suppressHydrationWarning>
      {compact ? formatAge(iso) : formatRelative(iso)}
    </time>
  );
}
