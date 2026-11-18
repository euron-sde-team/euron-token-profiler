"use client";

import { useEffect, useState } from "react";

/** The value, once it has stopped changing for `delay` ms: keeps typing from firing a query per key. */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
