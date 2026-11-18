/** The time ranges the dashboards offer; the API accepts the same keys. */
export const RANGES = [
  { value: "1h", label: "1 hour" },
  { value: "6h", label: "6 hours" },
  { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" },
  { value: "14d", label: "14 days" },
  { value: "30d", label: "30 days" },
] as const;

export type RangeKey = (typeof RANGES)[number]["value"];

export function isRange(value: string | null | undefined): value is RangeKey {
  return RANGES.some((range) => range.value === value);
}

/** The range from the address bar, or the page's default when it is missing or unknown. */
export function rangeOr(value: string | null | undefined, fallback: RangeKey): RangeKey {
  return isRange(value) ? value : fallback;
}
