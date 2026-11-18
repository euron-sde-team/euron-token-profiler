/** Small per-browser conveniences; storage can be unavailable, so every access is guarded. */
export const LAST_WORKSPACE_KEY = "tokenprofiler-last-workspace";
export const SEARCH_MODE_KEY = "tokenprofiler-search-mode";

export function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage blocked (private mode, policy): the preference just is not remembered.
  }
}

export function readJson<T>(key: string): T | null {
  const raw = readLocal(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function writeJson(key: string, value: unknown): void {
  writeLocal(key, JSON.stringify(value));
}
