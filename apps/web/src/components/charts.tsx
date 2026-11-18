"use client";

import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/cn";
import { formatCompact, formatNumber, formatPercent } from "@/lib/format";

/**
 * Chart helpers built on Recharts, themed through the CSS variables in globals.css (so light
 * and dark need no code) and made readable to assistive technology: every chart sits in a
 * `role="img"` frame named by its `label`, with the drawing itself hidden from the
 * accessibility tree. Put the numbers that matter in the label or a caption ("Peak: 42 on
 * Oct 12"), and show exact values in a table or list nearby when they matter.
 *
 *   <AreaTrend label="Tests run per day" data={daily} xKey="day" xFormat={formatDay}
 *              series={[{ key: "added", name: "Added", color: "var(--success)" }]} />
 */

export const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
];

export type Series = {
  /** The field of each data point. */
  key: string;
  /** The name shown in the legend and tooltip. */
  name: string;
  /** A CSS colour; defaults to the next chart series colour. */
  color?: string;
};

type Point = Record<string, string | number | null | undefined>;

type TrendProps = {
  data: Point[];
  xKey: string;
  series: Series[];
  /** Names the chart for assistive technology. */
  label: string;
  height?: number;
  xFormat?: (value: string) => string;
  yFormat?: (value: number) => string;
  /** Width reserved for the y axis labels; wider by default when `yFormat` adds units. */
  yWidth?: number;
  /** Allow fractional y ticks (money). Counts keep whole numbers only. */
  decimals?: boolean;
  /** How a value reads in the tooltip; defaults to yFormat. */
  valueFormat?: (value: number) => string;
  legend?: boolean;
  className?: string;
};

const axis = { fontSize: 11, fill: "var(--subtle)" };
const color = (series: Series, index: number): string => series.color ?? SERIES[index % SERIES.length]!;

type TooltipEntry = {
  name?: string | number;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
};

function ChartTooltip({
  active,
  payload,
  label,
  xFormat = (value) => value,
  valueFormat = formatNumber,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  xFormat?: (value: string) => string;
  valueFormat?: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-border bg-card max-w-72 rounded-lg border px-3 py-2 text-xs shadow-md">
      {label !== undefined ? <p className="mb-1 font-medium">{xFormat(String(label))}</p> : null}
      {payload.map((entry) => (
        <p key={String(entry.dataKey ?? entry.name)} className="text-muted-foreground flex items-center gap-2">
          <span className="size-2 shrink-0 rounded-full" style={{ background: entry.color }} aria-hidden />
          {entry.name}:{" "}
          <span className="text-foreground tabular font-medium">
            {typeof entry.value === "number" ? valueFormat(entry.value) : (entry.value ?? "")}
          </span>
        </p>
      ))}
    </div>
  );
}

/** A coloured dot and name per series, as a list (a legend that screen readers can read). */
export function ChartLegend({
  items,
  className,
}: {
  items: { name: string; color: string; value?: ReactNode }[];
  className?: string;
}) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs", className)}>
      {items.map((item) => (
        <li key={item.name} className="text-muted-foreground flex items-center gap-1.5">
          <span className="size-2 shrink-0 rounded-full" style={{ background: item.color }} aria-hidden />
          {item.name}
          {item.value !== undefined ? <span className="text-foreground tabular font-medium">{item.value}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function Frame({
  label,
  legend,
  series,
  className,
  children,
}: {
  label: string;
  legend: boolean;
  series: Series[];
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={className}>
      <div role="img" aria-label={label}>
        {children}
      </div>
      {legend && series.length > 1 ? (
        <ChartLegend
          className="mt-2 justify-center"
          items={series.map((s, index) => ({ name: s.name, color: color(s, index) }))}
        />
      ) : null}
    </div>
  );
}

function XAxisFor({ xKey, xFormat }: Pick<TrendProps, "xKey" | "xFormat">) {
  return (
    <XAxis
      dataKey={xKey}
      tickFormatter={xFormat}
      tick={axis}
      tickLine={false}
      axisLine={false}
      minTickGap={24}
      interval="preserveStartEnd"
    />
  );
}

function YAxisFor({ yFormat, yWidth, decimals }: Pick<TrendProps, "yFormat" | "yWidth" | "decimals">) {
  return (
    <YAxis
      allowDecimals={decimals ?? false}
      tickFormatter={yFormat ?? formatCompact}
      tick={axis}
      tickLine={false}
      axisLine={false}
      width={yWidth ?? (yFormat ? 60 : 44)}
    />
  );
}

/** Values over time as filled areas; `stacked` adds the series up. */
export function AreaTrend({
  data,
  xKey,
  series,
  label,
  height = 240,
  xFormat,
  yFormat,
  yWidth,
  decimals,
  valueFormat,
  legend = true,
  stacked = false,
  className,
}: TrendProps & { stacked?: boolean }) {
  return (
    <Frame label={label} legend={legend} series={series} className={className}>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer={false}>
          <defs>
            {series.map((s, index) => (
              <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color(s, index)} stopOpacity={0.4} />
                <stop offset="100%" stopColor={color(s, index)} stopOpacity={0.03} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxisFor xKey={xKey} xFormat={xFormat} />
          <YAxisFor yFormat={yFormat} yWidth={yWidth} decimals={decimals} />
          <Tooltip
            content={<ChartTooltip xFormat={xFormat} valueFormat={valueFormat ?? yFormat ?? formatNumber} />}
            cursor={{ stroke: "var(--input)" }}
          />
          {series.map((s, index) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stackId={stacked ? "stack" : undefined}
              stroke={color(s, index)}
              fill={`url(#fill-${s.key})`}
              strokeWidth={2}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </Frame>
  );
}

/** Columns per period; `stacked` splits each column by series (outcomes, categories). */
export function BarTrend({
  data,
  xKey,
  series,
  label,
  height = 240,
  xFormat,
  yFormat,
  yWidth,
  decimals,
  valueFormat,
  legend = true,
  stacked = false,
  className,
}: TrendProps & { stacked?: boolean }) {
  return (
    <Frame label={label} legend={legend} series={series} className={className}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer={false}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxisFor xKey={xKey} xFormat={xFormat} />
          <YAxisFor yFormat={yFormat} yWidth={yWidth} decimals={decimals} />
          <Tooltip
            content={<ChartTooltip xFormat={xFormat} valueFormat={valueFormat ?? yFormat ?? formatNumber} />}
            cursor={{ fill: "var(--muted)" }}
          />
          {series.map((s, index) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={color(s, index)}
              stackId={stacked ? "stack" : undefined}
              radius={stacked ? 0 : [3, 3, 0, 0]}
              maxBarSize={28}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  );
}

export type Slice = { name: string; value: number; color: string };

/**
 * Parts of a whole as a ring, with the total (or any text) in the middle and a legend that
 * lists every part with its count and share.
 */
export function DonutChart({
  slices,
  label,
  centerValue,
  centerLabel,
  size = 168,
  className,
}: {
  slices: Slice[];
  label: string;
  centerValue?: ReactNode;
  centerLabel?: string;
  size?: number;
  className?: string;
}) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  return (
    <div className={cn("flex flex-wrap items-center gap-x-8 gap-y-4", className)}>
      <div role="img" aria-label={label} className="relative shrink-0" style={{ width: size, height: size }}>
        <PieChart width={size} height={size} accessibilityLayer={false}>
          <Pie
            data={total > 0 ? slices : [{ name: "None", value: 1, color: "var(--muted)" }]}
            dataKey="value"
            nameKey="name"
            innerRadius={size * 0.32}
            outerRadius={size * 0.48}
            paddingAngle={total > 0 && slices.length > 1 ? 2 : 0}
            stroke="var(--card)"
            strokeWidth={2}
            isAnimationActive={false}
          >
            {(total > 0 ? slices : [{ color: "var(--muted)" }]).map((slice, index) => (
              <Cell key={index} fill={slice.color} />
            ))}
          </Pie>
        </PieChart>
        {centerValue !== undefined ? (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="tabular text-xl leading-none font-semibold">{centerValue}</span>
            {centerLabel ? <span className="text-muted-foreground mt-1 text-[11px]">{centerLabel}</span> : null}
          </div>
        ) : null}
      </div>
      <ul className="min-w-40 flex-1 space-y-1.5 text-[13px]">
        {slices.map((slice) => (
          <li key={slice.name} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: slice.color }} aria-hidden />
            <span className="text-muted-foreground min-w-0 flex-1 truncate">{slice.name}</span>
            <span className="tabular font-medium">{formatNumber(slice.value)}</span>
            <span className="text-muted-foreground tabular w-10 text-right text-xs">
              {total > 0 ? formatPercent(slice.value / total) : "0%"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
