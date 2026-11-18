"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";

import { mergeParams, type ParamUpdates } from "@/lib/url-params";

/**
 * Filter and page state that lives in the URL, so a view can be shared, bookmarked and
 * crawled (`?category=fact&user_id=amelia.novak&offset=50`). Updates replace the history
 * entry instead of adding one per keystroke. Changing a filter should reset `offset`:
 * `update({ category: ["fact"], offset: null })`.
 *
 * `useSearchParams` needs a Suspense boundary above the component that calls this hook
 * (Next.js requirement for pages that are prerendered): wrap the page body in `<Suspense>`.
 */
export function useUrlParams(): {
  params: URLSearchParams;
  get: (key: string) => string | null;
  getAll: (key: string) => string[];
  update: (updates: ParamUpdates) => void;
} {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  // Navigation is asynchronous: two updates in quick succession (a toggle, then typing) must
  // build on each other, not both on the address the first one has not reached yet.
  const pending = useRef<string | null>(null);
  const current = params.toString();
  useEffect(() => {
    pending.current = null;
  }, [current]);
  const update = useCallback(
    (updates: ParamUpdates) => {
      const base = pending.current ?? window.location.search;
      const query = mergeParams(new URLSearchParams(base), updates);
      pending.current = query;
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [router, pathname],
  );
  return {
    params,
    get: (key) => params.get(key),
    getAll: (key) => params.getAll(key),
    update,
  };
}
