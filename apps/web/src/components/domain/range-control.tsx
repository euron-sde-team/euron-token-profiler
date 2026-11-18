"use client";

import { SegmentedControl } from "@/components/ui/segmented-control";
import { RANGES, type RangeKey } from "@/lib/ranges";

export function RangeControl({
  value,
  onChange,
  options = RANGES.map((r) => r.value),
}: {
  value: RangeKey;
  onChange: (value: RangeKey) => void;
  options?: readonly RangeKey[];
}) {
  return (
    <SegmentedControl
      label="Time range"
      size="sm"
      value={value}
      onValueChange={onChange}
      options={RANGES.filter((r) => options.includes(r.value)).map((r) => ({
        value: r.value,
        label: r.value,
        ariaLabel: r.label,
      }))}
    />
  );
}
