import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "@/lib/cn";

/** The change from the previous period, coloured by whether a rise is good or bad. */
export function Delta({
  current,
  previous,
  higherIsBetter = false,
}: {
  current: number;
  previous: number;
  higherIsBetter?: boolean;
}) {
  if (previous === 0 && current === 0) return <span className="text-muted-foreground">no change</span>;
  if (previous === 0) return <span className="text-muted-foreground">new this period</span>;
  const change = (current - previous) / previous;
  if (Math.abs(change) < 0.005) {
    return (
      <span className="text-muted-foreground inline-flex items-center gap-0.5">
        <Minus className="size-3" aria-hidden /> flat vs previous
      </span>
    );
  }
  const up = change > 0;
  const good = up === higherIsBetter;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={cn("inline-flex items-center gap-0.5", good ? "text-success" : "text-danger")}>
      <Icon className="size-3" aria-hidden />
      {Math.abs(change * 100).toFixed(Math.abs(change) < 0.1 ? 1 : 0)}% {up ? "up" : "down"} vs previous
    </span>
  );
}
