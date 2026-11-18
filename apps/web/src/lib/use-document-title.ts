"use client";

import { useEffect } from "react";

import { runtimeEnv } from "@/lib/runtime-env";

/** Sets the browser tab title to "<title> | <product name>" while the page is mounted. */
export function useDocumentTitle(title: string | undefined): void {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = `${title} | ${runtimeEnv().productName}`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
