import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

/**
 * One headline number with a label, an optional icon and a caption ("12 more than last
 * week"). `children` is for a sparkline or a small bar under the number.
 */
export function StatCard({
  label,
  value,
  caption,
  icon,
  children,
  className,
}: {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  icon?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-muted-foreground text-[13px]">{label}</p>
        {icon ? (
          <span className="bg-accent text-accent-foreground flex size-7 shrink-0 items-center justify-center rounded-lg [&_svg]:size-4">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="tabular mt-1.5 text-[26px] leading-none font-semibold tracking-tight">{value}</p>
      {caption ? <p className="text-muted-foreground mt-2 text-xs">{caption}</p> : null}
      {children ? <div className="mt-3">{children}</div> : null}
    </Card>
  );
}
