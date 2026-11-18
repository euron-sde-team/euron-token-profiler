"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { toast, Toaster } from "sonner";

import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const PUBLIC_PATHS = ["/login", "/welcome"];

/** The session ended or was never there: sign in again, and come back to this page. */
function leaveForSignIn(error: unknown, queryKey?: readonly unknown[]): boolean {
  if (!(error instanceof ApiError) || error.status !== 401) return false;
  // A wrong password is also a 401; the form shows that one itself. The `me` query is
  // watched by the pages that need it.
  if (error.code === "invalid_credentials" || queryKey?.[0] === "me") return true;
  const path = window.location.pathname;
  if (!PUBLIC_PATHS.some((prefix) => path.startsWith(prefix))) {
    const next = encodeURIComponent(path + window.location.search);
    window.location.replace(`/login?next=${next}`);
  }
  return true;
}

function reportFailure(error: unknown): void {
  if (!(error instanceof ApiError)) {
    toast.error(error instanceof Error ? error.message : "Something went wrong.");
    return;
  }
  // Support needs the request id of a server failure; a validation message does not.
  toast.error(error.message, {
    description: error.status >= 500 && error.requestId ? `Request ${error.requestId}` : undefined,
  });
}

function makeClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        leaveForSignIn(error, query.queryKey);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (leaveForSignIn(error) || mutation.meta?.silent) return;
        reportFailure(error);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        // Retry transient server failures only; a 4xx will not change on retry.
        retry: (count, error) => error instanceof ApiError && (error.status === 0 || error.status >= 500) && count < 2,
      },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  // Subscribing here also keeps the page in step with the operating system while the
  // theme is "system", whichever page is open.
  const { resolved } = useTheme();
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
      <Toaster
        theme={resolved}
        position="bottom-right"
        richColors
        closeButton
        toastOptions={{ className: "text-[13px]" }}
      />
    </QueryClientProvider>
  );
}
