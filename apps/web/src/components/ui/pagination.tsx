import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/cn";

/**
 * "51-100 of 412 memories" with previous and next buttons, for the API's limit/offset
 * pages. Renders nothing for an empty list; hide it yourself when everything fits one page.
 */
export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
  noun = "items",
  className,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
  noun?: string;
  className?: string;
}) {
  if (total === 0) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav aria-label="Pagination" className={cn("flex flex-wrap items-center justify-between gap-3", className)}>
      <p className="text-muted-foreground tabular text-[13px]" aria-live="polite">
        {formatNumber(from)}-{formatNumber(to)} of {formatNumber(total)} {noun}
      </p>
      <div className="flex items-center gap-1.5">
        <Button
          variant="secondary"
          size="sm"
          disabled={offset <= 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          <ChevronLeft /> Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={offset + limit >= total}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next <ChevronRight />
        </Button>
      </div>
    </nav>
  );
}
