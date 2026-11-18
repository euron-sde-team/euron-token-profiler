import { cn } from "@/lib/cn";

/** A flame graph: stacked bars of different lengths, the shape of a trace. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={cn("size-7", className)}>
      <rect width="64" height="64" rx="16" fill="var(--primary)" />
      <g fill="var(--primary-foreground)">
        <rect x="13" y="14" width="38" height="7" rx="3.5" />
        <rect x="13" y="25" width="24" height="7" rx="3.5" opacity="0.9" />
        <rect x="31" y="36" width="20" height="7" rx="3.5" opacity="0.8" />
        <rect x="19" y="47" width="14" height="7" rx="3.5" opacity="0.7" />
      </g>
    </svg>
  );
}

export function Wordmark({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-[15px] font-semibold tracking-tight">{name}</span>
    </span>
  );
}
