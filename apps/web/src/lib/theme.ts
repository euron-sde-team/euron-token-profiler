"use client";

import { useCallback, useSyncExternalStore } from "react";

import { STORAGE_KEY } from "@/lib/theme-script";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export function parseTheme(raw: string | null | undefined): ThemePreference {
  return raw === "light" || raw === "dark" ? raw : "system";
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): ResolvedTheme {
  if (preference === "system") return prefersDark ? "dark" : "light";
  return preference;
}

const DARK_QUERY = "(prefers-color-scheme: dark)";
const listeners = new Set<() => void>();

function stored(): ThemePreference {
  try {
    return parseTheme(localStorage.getItem(STORAGE_KEY));
  } catch {
    return "system";
  }
}

function apply(preference: ThemePreference): void {
  const dark = resolveTheme(preference, matchMedia(DARK_QUERY).matches) === "dark";
  document.documentElement.classList.toggle("dark", dark);
}

function notify(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const media = matchMedia(DARK_QUERY);
  // Follow the operating system while the choice is "system", and follow other tabs.
  const onSystemChange = () => {
    apply(stored());
    notify();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) onSystemChange();
  };
  media.addEventListener("change", onSystemChange);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onSystemChange);
    window.removeEventListener("storage", onStorage);
  };
}

// One string snapshot ("system:dark") so the store compares by value and never loops.
function snapshot(): string {
  return `${stored()}:${document.documentElement.classList.contains("dark") ? "dark" : "light"}`;
}

export function useTheme(): {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setTheme: (next: ThemePreference) => void;
} {
  const value = useSyncExternalStore(subscribe, snapshot, () => "system:light");
  const [preference, resolved] = value.split(":") as [ThemePreference, ResolvedTheme];
  const setTheme = useCallback((next: ThemePreference) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode or blocked storage: the choice still applies to this page view.
    }
    apply(next);
    notify();
  }, []);
  return { preference, resolved, setTheme };
}
