import { Gauge, ScrollText, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/brand";
import { ThemeMenu } from "@/components/shell/theme-menu";

const FEATURES = [
  {
    icon: Wallet,
    title: "Cost where it belongs",
    text: "Tokens and dollars per prompt, model, agent and tool, from a price table you can override.",
  },
  {
    icon: Gauge,
    title: "Latency and errors at a glance",
    text: "p50, p95 and p99 over time, failing spans in context, and alerts when a budget or a rule trips.",
  },
  {
    icon: ScrollText,
    title: "Prompts with a history",
    text: "Versions, labels and what each version cost in production, fetched by your SDK.",
  },
];

/** Decorative: one agent run as a waterfall, with the tools and model calls inside it. */
function TraceSample() {
  const rows = [
    { name: "support-agent", detail: "3.4 s", left: "0%", width: "100%", indent: 0 },
    { name: "classify-intent", detail: "$0.0004", left: "2%", width: "14%", indent: 1 },
    { name: "vector_search", detail: "210 ms", left: "17%", width: "9%", indent: 1 },
    { name: "draft-reply", detail: "$0.0121", left: "28%", width: "68%", indent: 1 },
  ];
  return (
    <div aria-hidden className="relative mt-8 rounded-2xl border border-white/15 bg-white/[0.07] p-4 backdrop-blur-sm">
      <p className="text-[11px] font-medium tracking-wider text-white/60 uppercase">One request, four spans</p>
      <ul className="mt-3 space-y-1.5">
        {rows.map((row) => (
          <li key={row.name} className="rounded-lg bg-black/25 px-3 py-2">
            <div className="flex items-center justify-between" style={{ paddingLeft: row.indent * 12 }}>
              <span className="font-mono text-[12px] text-white/90">{row.name}</span>
              <span className="rounded bg-emerald-400/20 px-1.5 py-0.5 text-[11px] text-emerald-200">{row.detail}</span>
            </div>
            <div className="relative mt-1.5 h-1 rounded-full bg-white/10">
              <div className="absolute h-1 rounded-full bg-teal-300/80" style={{ left: row.left, width: row.width }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The split layout of the sign-in and first-run pages: a brand panel on large screens, the
 * form column everywhere. Children are the form.
 */
export function AuthLayout({ productName, children }: { productName: string; children: ReactNode }) {
  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <section className="relative hidden overflow-hidden bg-[#051a19] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(60% 50% at 10% 0%, rgb(20 184 166 / 0.45), transparent 70%), radial-gradient(50% 45% at 100% 100%, rgb(99 102 241 / 0.22), transparent 70%)",
          }}
        />
        <Wordmark name={productName} className="relative [&_span]:text-white" />
        <div className="relative max-w-md">
          <h2 className="text-[34px] leading-tight font-semibold tracking-tight">
            See what every token does and what it costs.
          </h2>
          <p className="mt-3 text-[15px] text-white/75">
            Traces, token and cost attribution, prompts, budgets and alerts for LLM applications, on infrastructure you
            own.
          </p>
          <TraceSample />
          <ul className="mt-8 space-y-4">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span>
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block text-[13px] text-white/70">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-white/60">Open source under the MIT License.</p>
      </section>
      <section className="relative flex items-center justify-center p-6 sm:p-12">
        <div className="absolute top-4 right-4">
          <ThemeMenu />
        </div>
        <div className="w-full max-w-sm">
          <Wordmark name={productName} className="mb-10 lg:hidden" />
          {children}
        </div>
      </section>
    </main>
  );
}
