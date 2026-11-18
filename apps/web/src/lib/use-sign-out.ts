"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { useLogout } from "@/lib/queries";

/**
 * Sign out of this browser. It leaves the page first, so nothing still mounted asks the API
 * for a session that is ending, then ends the session (the cached data is dropped when the
 * request settles). A failed request is ignored: the sign-in page is the right place to be.
 */
export function useSignOut(): { signOut: () => Promise<void>; pending: boolean } {
  const router = useRouter();
  const logout = useLogout();
  const signOut = useCallback(async () => {
    router.replace("/login");
    await logout.mutateAsync().catch(() => undefined);
  }, [router, logout]);
  return { signOut, pending: logout.isPending };
}
