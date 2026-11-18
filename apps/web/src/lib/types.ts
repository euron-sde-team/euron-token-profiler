/** Shapes of the TokenProfiler API (control plane, /api/v1), as the web app uses them. */

export type Role = "admin" | "member" | "viewer";

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type User = {
  id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type SessionOut = { user: User; token: string; expires_at: string };
export type UserCreated = { user: User; temporary_password: string };

export type SystemInfo = {
  product_name: string;
  version: string;
  needs_setup: boolean;
  allow_signup: boolean;
  archive_store: string;
  default_retention_days: number;
  ingest_rate_limit: number;
  dashboard_cache_ttl_s: number;
  api_url: string;
};

/** Decimals arrive as strings so no precision is lost; convert at the edge of a calculation. */
export type Decimal = string;

export type CustomRule = { name: string; pattern: string; replacement: string };

export type RedactionRules = {
  detectors: string[];
  custom: CustomRule[];
  store_payloads: boolean;
  max_payload_chars: number;
  redact_metadata: boolean;
};

export type Project = {
  id: string;
  name: string;
  slug: string;
  description: string;
  sampling_rate: Decimal;
  keep_errors: boolean;
  keep_slow_ms: number | null;
  redaction: RedactionRules;
  retention_days: number;
  archive_before_delete: boolean;
  has_webhook: boolean;
  created_at: string;
  traces_7d: number;
};

export type ProjectUpdate = Partial<
  Pick<Project, "name" | "description" | "keep_errors" | "keep_slow_ms" | "retention_days" | "archive_before_delete">
> & {
  sampling_rate?: number;
  clear_keep_slow?: boolean;
  redaction?: RedactionRules;
  webhook_url?: string;
};

export type ProjectKey = {
  id: string;
  name: string;
  prefix: string;
  created_by_name: string | null;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};
export type ProjectKeyCreated = ProjectKey & { key: string };

export type Trace = {
  id: string;
  name: string;
  user_id: string | null;
  session_id: string | null;
  environment: string;
  release: string | null;
  tags: string[];
  started_at: string;
  ended_at: string;
  duration_ms: number;
  status: "ok" | "error";
  span_count: number;
  error_count: number;
  generation_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: Decimal;
  models: string[];
  agents: string[];
  tools: string[];
  prompts: string[];
};

export type TraceDetail = Trace & { input: string | null; output: string | null; metadata: Record<string, unknown> };

export type SpanKind = "span" | "generation" | "embedding" | "agent" | "tool" | "retriever";

export type Span = {
  id: string;
  parent_id: string | null;
  name: string;
  kind: SpanKind;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  time_to_first_token_ms: number | null;
  status: "ok" | "error";
  status_message: string | null;
  level: string;
  agent_name: string | null;
  tool_name: string | null;
  prompt_name: string | null;
  prompt_version: number | null;
  model: string | null;
  provider: string | null;
  model_parameters: Record<string, unknown>;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  total_tokens: number;
  usage_estimated: boolean;
  input_cost: Decimal;
  output_cost: Decimal;
  total_cost: Decimal;
  cost_source: "reported" | "table" | "none" | null;
  input: string | null;
  output: string | null;
  metadata: Record<string, unknown>;
  redactions: number;
};

export type TraceWithSpans = { trace: TraceDetail; spans: Span[] };
export type TracePage = Page<Trace> & { total_capped: boolean };

export type Facets = {
  models: string[];
  agents: string[];
  tools: string[];
  prompts: string[];
  tags: string[];
  environments: string[];
};

export type Kpis = {
  traces: number;
  errors: number;
  error_rate: number;
  cost: Decimal;
  input_tokens: number;
  output_tokens: number;
  generations: number;
  users: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  avg_cost_per_trace: Decimal;
};

export type SeriesPoint = {
  at: string;
  traces: number;
  errors: number;
  error_rate: number;
  cost: Decimal;
  input_tokens: number;
  output_tokens: number;
  p50_ms: number;
  p95_ms: number;
};

export type CostPoint = { at: string; values: Record<string, Decimal> };

export type Overview = {
  start: string;
  end: string;
  bucket_seconds: number;
  current: Kpis;
  previous: Kpis;
  series: SeriesPoint[];
  cost_by_model: CostPoint[];
  top_models: string[];
  generated_at: string;
  cached: boolean;
};

export type Dimension = "model" | "agent" | "tool" | "prompt";

export type BreakdownItem = {
  key: string;
  version: number | null;
  calls: number;
  errors: number;
  error_rate: number;
  p50_ms: number;
  p95_ms: number;
  generations: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost: Decimal;
  cost_share: number;
  avg_cost_per_call: Decimal;
  avg_ttft_ms: number | null;
  last_seen: string;
};

export type Breakdown = {
  dimension: Dimension;
  start: string;
  end: string;
  total_cost: Decimal;
  items: BreakdownItem[];
  generated_at: string;
  cached: boolean;
};

export type PromptUsage = {
  calls: number;
  errors: number;
  error_rate: number;
  cost: Decimal;
  input_tokens: number;
  output_tokens: number;
  avg_tokens: number;
  p50_ms: number;
  p95_ms: number;
  last_seen: string | null;
};

export type PromptSummary = {
  name: string;
  latest_version: number;
  versions: number;
  labels: string[];
  managed: boolean;
  usage: PromptUsage;
  updated_at: string;
};

export type PromptVersion = {
  version: number;
  template: string | null;
  config: Record<string, unknown>;
  labels: string[];
  commit_message: string | null;
  managed: boolean;
  created_at: string;
  usage: PromptUsage;
};

export type PromptDetail = { name: string; versions: PromptVersion[]; usage: PromptUsage };

export type Price = {
  id: string;
  model: string;
  match_pattern: string;
  provider: string;
  input_per_mtok: Decimal;
  output_per_mtok: Decimal;
  cached_input_per_mtok: Decimal | null;
  source: "builtin" | "custom";
  scope: "shared" | "project";
  overridden: boolean;
  updated_at: string;
};

export type BudgetScope = "project" | "model" | "agent" | "tool" | "prompt";
export type BudgetPeriod = "day" | "week" | "month";

export type Budget = {
  id: string;
  name: string;
  scope: BudgetScope;
  scope_value: string | null;
  period: BudgetPeriod;
  limit_usd: Decimal;
  warn_at_percent: number;
  enabled: boolean;
  spent_usd: Decimal;
  percent_used: number;
  period_start: string;
  period_end: string;
  state: "ok" | "warning" | "exceeded";
};

export type BudgetWrite = {
  name: string;
  scope: BudgetScope;
  scope_value: string | null;
  period: BudgetPeriod;
  limit_usd: string;
  warn_at_percent: number;
  enabled: boolean;
};

export type RuleMetric = "error_rate" | "p95_latency_ms" | "cost_usd" | "trace_count";

export type AlertRule = {
  id: string;
  name: string;
  metric: RuleMetric;
  comparator: "above" | "below";
  threshold: Decimal;
  window_minutes: number;
  min_traces: number;
  severity: "warning" | "critical";
  enabled: boolean;
  firing: boolean;
};

export type RuleWrite = Omit<AlertRule, "id" | "firing" | "threshold"> & { threshold: string };

export type AlertsOverview = { budgets: Budget[]; rules: AlertRule[]; firing: number };

export type AlertEvent = {
  id: string;
  kind: "budget" | "rule";
  source_id: string;
  source_name: string;
  severity: "warning" | "critical";
  state: "firing" | "resolved";
  value: Decimal;
  threshold: Decimal;
  message: string;
  fired_at: string;
  resolved_at: string | null;
  notified_at: string | null;
  notify_error: string | null;
};

export type AuditEvent = {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  project_id: string | null;
  details: Record<string, unknown>;
  actor_name: string | null;
  created_at: string;
};

export type ArchiveObject = { key: string; size_bytes: number };
export type RedactionTestResult = { redacted: string; redactions: number; by_rule: Record<string, number> };
