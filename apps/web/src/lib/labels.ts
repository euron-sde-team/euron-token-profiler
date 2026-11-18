import type { BudgetPeriod, BudgetScope, Dimension, RuleMetric, Role, SpanKind } from "@/lib/types";

export type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "primary";

export const SPAN_KIND: Record<SpanKind, { label: string; tone: Tone }> = {
  span: { label: "Span", tone: "neutral" },
  generation: { label: "Generation", tone: "primary" },
  embedding: { label: "Embedding", tone: "info" },
  agent: { label: "Agent", tone: "warning" },
  tool: { label: "Tool", tone: "success" },
  retriever: { label: "Retriever", tone: "info" },
};

/** The colour of a span in the waterfall, by kind (CSS variables from globals.css). */
export const SPAN_COLOR: Record<SpanKind, string> = {
  span: "var(--series-6)",
  generation: "var(--series-1)",
  embedding: "var(--series-5)",
  agent: "var(--series-3)",
  tool: "var(--series-2)",
  retriever: "var(--series-4)",
};

export const DIMENSION_LABEL: Record<Dimension, string> = {
  model: "Model",
  agent: "Agent",
  tool: "Tool",
  prompt: "Prompt",
};

export const BUDGET_SCOPE: Record<BudgetScope, string> = {
  project: "Whole project",
  model: "One model",
  agent: "One agent",
  tool: "One tool",
  prompt: "One prompt",
};

export const BUDGET_PERIOD: Record<BudgetPeriod, string> = { day: "Daily", week: "Weekly", month: "Monthly" };

export const BUDGET_STATE: Record<"ok" | "warning" | "exceeded", { label: string; tone: Tone }> = {
  ok: { label: "On track", tone: "success" },
  warning: { label: "Nearing limit", tone: "warning" },
  exceeded: { label: "Exceeded", tone: "danger" },
};

export const RULE_METRIC: Record<RuleMetric, { label: string; unit: string }> = {
  error_rate: { label: "Error rate", unit: "%" },
  p95_latency_ms: { label: "p95 latency", unit: "ms" },
  cost_usd: { label: "Spend", unit: "USD" },
  trace_count: { label: "Trace count", unit: "traces" },
};

export const SEVERITY: Record<"warning" | "critical", { label: string; tone: Tone }> = {
  warning: { label: "Warning", tone: "warning" },
  critical: { label: "Critical", tone: "danger" },
};

export const ROLE: Record<Role, { label: string; description: string }> = {
  admin: { label: "Admin", description: "Everything: people, projects, redaction, retention and webhooks." },
  member: { label: "Member", description: "Prompts, prices, budgets, alert rules and project keys." },
  viewer: { label: "Viewer", description: "Read only: traces, dashboards and prompts." },
};

export const DETECTOR_LABEL: Record<string, string> = {
  email: "Email addresses",
  credit_card: "Card numbers (checksum verified)",
  ssn: "US social security numbers",
  phone: "Phone numbers",
  ipv4: "IPv4 addresses",
  api_key: "API keys and tokens",
  jwt: "JSON web tokens",
};

export const AUDIT_LABEL: Record<string, string> = {
  "user.created": "added the person",
  "user.updated": "changed the person",
  "project.created": "created the project",
  "project.updated": "changed the project settings",
  "project.deleted": "deleted the project",
  "api_key.created": "created the API key",
  "api_key.revoked": "revoked the API key",
  "prompt.version_created": "saved a prompt version",
  "prompt.label_moved": "moved a prompt label",
  "price.created": "added a price override",
  "price.updated": "changed a price override",
  "price.deleted": "removed a price override",
  "budget.created": "created the budget",
  "budget.updated": "changed the budget",
  "budget.deleted": "deleted the budget",
  "alert_rule.created": "created the alert rule",
  "alert_rule.updated": "changed the alert rule",
  "alert_rule.deleted": "deleted the alert rule",
};
