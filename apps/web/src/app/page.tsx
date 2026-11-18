"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ErrorState, Spinner } from "@/components/ui/feedback";
import { ApiError } from "@/lib/api";
import { useMe, useSystemInfo } from "@/lib/queries";

/** Sends people where they belong: first-run setup, sign-in, or the overview. */
export default function Home() {
  const router = useRouter();
  const system = useSystemInfo();
  // A fresh deployment has nobody to sign in: do not ask who is signed in until it is set up.
  const me = useMe(system.data?.needs_setup === false);
  const settled = !system.isFetching && !me.isFetching;
  const unauthorized = me.error instanceof ApiError && me.error.status === 401;

  useEffect(() => {
    // Decide only on fresh answers: a refetch after signing in still holds the old 401.
    if (!settled) return;
    if (system.data?.needs_setup) router.replace("/welcome");
    else if (system.data && unauthorized) router.replace("/login");
    else if (me.data) router.replace("/overview");
  }, [settled, system.data, unauthorized, me.data, router]);

  const failure = system.error ?? (unauthorized ? null : me.error);
  if (failure) {
    return (
      <main>
        <ErrorState
          className="min-h-dvh"
          title="TokenProfiler is unreachable"
          message={failure.message}
          onRetry={() => {
            void system.refetch();
            void me.refetch();
          }}
        />
      </main>
    );
  }
  return (
    <main className="flex min-h-dvh items-center justify-center" role="status" aria-label="Loading">
      <Spinner className="size-5" />
    </main>
  );
}
