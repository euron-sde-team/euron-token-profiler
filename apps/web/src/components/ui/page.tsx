"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { useDocumentTitle } from "@/lib/use-document-title";

export type Crumb = { label: string; href?: string };

/** "Memories / Is vegetarian": where a detail page sits. The last crumb is the current page. */
export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn("mb-2", className)}>
      <ol className="text-muted-foreground flex flex-wrap items-center gap-1 text-[12.5px]">
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="flex min-w-0 items-center gap-1">
              {item.href && !last ? (
                <Link href={item.href} className="hover:text-foreground truncate transition-colors">
                  {item.label}
                </Link>
              ) : (
                <span
                  className={cn("max-w-64 truncate", last && "text-foreground")}
                  aria-current={last ? "page" : undefined}
                >
                  {item.label}
                </span>
              )}
              {last ? null : <ChevronRight className="text-subtle size-3.5 shrink-0" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * The title block at the top of every page, with optional breadcrumbs and actions. A string
 * title also becomes the browser tab title ("Memories | Euron MemoryVault"); pass
 * `documentTitle` when the title is not a plain string.
 */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumbs,
  documentTitle,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumbs?: Crumb[];
  documentTitle?: string;
  className?: string;
}) {
  useDocumentTitle(documentTitle ?? (typeof title === "string" ? title : undefined));
  return (
    <header className={cn("pb-6", className)}>
      {breadcrumbs?.length ? <Breadcrumbs items={breadcrumbs} /> : null}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight break-words">{title}</h1>
          {description ? <p className="text-muted-foreground mt-1 text-[13.5px]">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}

/** The padded, centred content column of a page. Pass `className="max-w-4xl"` to narrow it. */
export function PageBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8", className)}>{children}</div>;
}
