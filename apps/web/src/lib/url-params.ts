export type ParamUpdates = Record<string, string | number | boolean | readonly string[] | null | undefined>;

/**
 * The query string after applying `updates` to `current`: a null, undefined, empty or false
 * value removes the key, an array repeats it, anything else replaces it. Pure, so it is
 * tested; `useUrlParams` is the hook around it.
 */
export function mergeParams(current: URLSearchParams, updates: ParamUpdates): string {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(updates)) {
    next.delete(key);
    if (value === null || value === undefined || value === "" || value === false) continue;
    if (Array.isArray(value)) {
      for (const item of value) next.append(key, item);
    } else {
      next.append(key, String(value));
    }
  }
  return next.toString();
}
