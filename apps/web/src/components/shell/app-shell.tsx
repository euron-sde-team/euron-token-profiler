"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Wordmark } from "@/components/brand";
import { isNavActive, NAV_GROUPS } from "@/components/shell/nav";
import { ThemeMenu } from "@/components/shell/theme-menu";
import { UserMenu } from "@/components/shell/user-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorState, Spinner } from "@/components/ui/feedback";
import { NativeSelect } from "@/components/ui/input";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { ProjectProvider, useProject } from "@/lib/project";
import { useAlerts, useMe } from "@/lib/queries";
import { runtimeEnv } from "@/lib/runtime-env";
import type { User } from "@/lib/types";

function ProjectSwitcher() {
  const { project, projects, select } = useProject();
  return (
    <div className="px-4 pb-1">
      <label
        htmlFor="project-switcher"
        className="text-subtle block pb-1 text-[11px] font-medium tracking-wider uppercase"
      >
        Project
      </label>
      <NativeSelect
        id="project-switcher"
        value={project.id}
        onChange={(event) => select(event.target.value)}
        className="h-8 text-[13px]"
      >
        {projects.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </NativeSelect>
    </div>
  );
}

function Sidebar({ account, onNavigate }: { account: User; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { project } = useProject();
  const alerts = useAlerts(project.id);
  const firing = alerts.data?.firing ?? 0;
  return (
    <div className="border-sidebar-border bg-sidebar flex h-full w-64 flex-col border-r">
      <div className="px-4 pt-4 pb-3">
        <Wordmark name={runtimeEnv().productName} />
      </div>
      <ProjectSwitcher />
      <nav className="scroll-quiet mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-3" aria-label="Main">
        {NAV_GROUPS.map((group, index) => (
          <div key={group.label ?? index} className={cn(index > 0 && "mt-4")}>
            {group.label ? (
              <p className="text-subtle px-2.5 pb-1 text-[11px] font-medium tracking-wider uppercase">{group.label}</p>
            ) : null}
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = isNavActive(pathname, href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors [&_svg]:size-4",
                        active
                          ? "bg-card text-foreground ring-border font-medium shadow-sm ring-1"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon className={active ? "text-primary" : ""} aria-hidden />
                      {label}
                      {href === "/budgets" && firing > 0 ? (
                        <Badge tone="danger" className="ml-auto" aria-label={`${firing} alerts firing`}>
                          {firing}
                        </Badge>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-sidebar-border border-t p-3">
        <UserMenu account={account} />
      </div>
    </div>
  );
}

/**
 * The frame of every signed-in page: a sidebar (a drawer on phones) and the user menu. It
 * loads the signed-in person first and sends everyone else to the sign-in page, remembering
 * where they were going.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <SignedIn>
      {(account) => (
        <ProjectProvider>
          <Frame account={account}>{children}</Frame>
        </ProjectProvider>
      )}
    </SignedIn>
  );
}

function SignedIn({ children }: { children: (account: User) => ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  // A refetch after signing in still carries the old 401 until it answers: wait for it.
  const unauthorized = me.error instanceof ApiError && me.error.status === 401 && !me.isFetching;

  useEffect(() => {
    if (unauthorized) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [unauthorized, pathname, router]);

  if (me.isLoading || (me.isFetching && !me.data) || unauthorized) {
    return (
      <div className="flex h-dvh items-center justify-center" role="status" aria-label="Loading">
        <Spinner className="size-5" />
      </div>
    );
  }
  if (me.error || !me.data) {
    return (
      <ErrorState
        className="h-dvh"
        title="TokenProfiler is unreachable"
        message={me.error?.message ?? "Try again shortly."}
        onRetry={() => me.refetch()}
      />
    );
  }

  return <>{children(me.data)}</>;
}

function Frame({ account, children }: { account: User; children: ReactNode }) {
  const pathname = usePathname();
  // The path the drawer was opened on: navigating elsewhere closes it without an effect.
  const [drawerPath, setDrawerPath] = useState<string | null>(null);
  const drawer = drawerPath === pathname;
  return (
    <div className="flex h-dvh overflow-hidden">
      <a
        href="#main"
        className="bg-card text-foreground ring-ring sr-only z-50 rounded-lg px-3 py-2 text-sm font-medium shadow-md ring-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <aside className="hidden shrink-0 lg:block">
        <Sidebar account={account} />
      </aside>
      <Sheet open={drawer} onOpenChange={(open) => setDrawerPath(open ? pathname : null)}>
        <SheetContent side="left" title="Navigation" hideTitle showClose={false} className="w-64 border-x-0 p-0">
          <Sidebar account={account} onNavigate={() => setDrawerPath(null)} />
        </SheetContent>
      </Sheet>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border bg-card flex h-12 shrink-0 items-center justify-between border-b px-3 lg:hidden">
          <Button variant="ghost" size="icon-sm" aria-label="Open menu" onClick={() => setDrawerPath(pathname)}>
            <Menu />
          </Button>
          <Wordmark name={runtimeEnv().productName} className="[&_svg]:size-6" />
          <ThemeMenu />
        </header>
        <main id="main" tabIndex={-1} className="scroll-quiet min-h-0 flex-1 overflow-y-auto outline-none">
          {children}
        </main>
      </div>
    </div>
  );
}
