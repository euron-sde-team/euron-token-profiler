import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

/**
 * Tables scroll sideways inside their own container on a phone. The container is a labelled,
 * focusable region (so keyboard users can scroll it, which axe checks): always give `label`.
 * It is positioned so that visually hidden text inside it (an `sr-only` header) is clipped here
 * and cannot widen the page.
 *
 *   <TableContainer label="Memories">
 *     <Table>
 *       <TableHeader><TableRow><TableHead>Memory</TableHead></TableRow></TableHeader>
 *       <TableBody>...</TableBody>
 *     </Table>
 *   </TableContainer>
 */
export function TableContainer({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className={cn(
        "border-border bg-card scroll-quiet relative overflow-x-auto rounded-xl border shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Table({ className, ...props }: ComponentProps<"table">) {
  return <table className={cn("w-full caption-bottom text-[13px]", className)} {...props} />;
}

export function TableHeader({ className, ...props }: ComponentProps<"thead">) {
  return <thead className={cn("bg-muted/60 border-border border-b", className)} {...props} />;
}

export function TableBody({ className, ...props }: ComponentProps<"tbody">) {
  return <tbody className={cn("divide-border divide-y", className)} {...props} />;
}

export function TableRow({ className, ...props }: ComponentProps<"tr">) {
  return (
    <tr
      className={cn("hover:bg-muted/50 data-[state=selected]:bg-accent/60 transition-colors", className)}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: ComponentProps<"th">) {
  return (
    <th
      scope="col"
      className={cn(
        "text-muted-foreground h-9 px-4 text-left align-middle text-xs font-medium whitespace-nowrap",
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: ComponentProps<"td">) {
  return <td className={cn("px-4 py-3 align-middle", className)} {...props} />;
}
