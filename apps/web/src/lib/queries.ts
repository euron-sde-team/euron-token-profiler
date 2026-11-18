"use client";

/**
 * Data access for the whole dashboard: one TanStack Query hook per API endpoint.
 *
 * CONVENTIONS
 *
 * Layout. Pages live in `app/(app)/<route>/page.tsx` and stay thin; feature UI goes in
 * `components/<area>/`. Shared building blocks are `components/ui/*` (primitives) and
 * `components/domain/*`. Design tokens are CSS variables in `app/globals.css`; use the
 * Tailwind names (`bg-card`, `text-muted-foreground`), never raw colours.
 *
 * Projects. Everything below `/projects/{id}` takes the project id first. Pages get the
 * selected project from `useProject()` and pass its id; a query stays disabled until it
 * has one.
 *
 * Roles. `useCan("member")` hides the controls a viewer may not use. The API enforces the
 * same rules; the UI only avoids offering what would be refused.
 *
 * Keys. `qk` builds every query key; the resource name is always the first element, so
 * `invalidateQueries({ queryKey: ["prompts"] })` refreshes every prompt list and detail.
 *
 * Writes. A mutation hook returns the `useMutation` result: call `mutateAsync` in a handler.
 * Success toasts belong to the call site. Failures are toasted for you by the QueryClient's
 * mutation cache (see `lib/providers.tsx`); pass `{ silent: true }` when the form renders
 * `mutation.error` inline.
 *
 * Dashboards poll every 30 s; the server caches their aggregates for the same time.
 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toQuery, V1, type QueryValue } from "@/lib/api";
import type {
  AlertEvent,
  AlertRule,
  AlertsOverview,
  ArchiveObject,
  AuditEvent,
  Breakdown,
  Budget,
  BudgetWrite,
  Dimension,
  Facets,
  Overview,
  Page,
  Price,
  Project,
  ProjectKey,
  ProjectKeyCreated,
  ProjectUpdate,
  PromptDetail,
  PromptSummary,
  PromptVersion,
  RedactionRules,
  RedactionTestResult,
  Role,
  RuleWrite,
  SessionOut,
  SystemInfo,
  TracePage,
  TraceWithSpans,
  User,
  UserCreated,
} from "@/lib/types";

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: { silent?: boolean };
  }
}

/** Pass `{ silent: true }` when the form shows the error itself. */
export type HookOptions = { silent?: boolean };

const meta = (options?: HookOptions) => ({ silent: options?.silent ?? false });

export type PageParams = { limit?: number; offset?: number };
export type TraceParams = PageParams & Record<string, QueryValue>;

export const qk = {
  system: ["system"] as const,
  me: ["me"] as const,
  users: ["users"] as const,
  projects: ["projects"] as const,
  keys: (project: string, params: PageParams = {}) => ["keys", project, params] as const,
  traces: (project: string, params: TraceParams = {}) => ["traces", project, "list", params] as const,
  trace: (project: string, id: string) => ["traces", project, "one", id] as const,
  facets: (project: string) => ["traces", project, "facets"] as const,
  overview: (project: string, range: string, environment?: string) =>
    ["metrics", project, "overview", range, environment ?? "all"] as const,
  breakdown: (project: string, dimension: Dimension, range: string) =>
    ["metrics", project, "breakdown", dimension, range] as const,
  prompts: (project: string, range: string, params: PageParams = {}) =>
    ["prompts", project, "list", range, params] as const,
  prompt: (project: string, name: string, range: string) => ["prompts", project, "one", name, range] as const,
  prices: (project: string) => ["prices", project] as const,
  alerts: (project: string) => ["alerts", project, "overview"] as const,
  alertEvents: (project: string, params: PageParams & { firing_only?: boolean } = {}) =>
    ["alerts", project, "events", params] as const,
  audit: (project: string | undefined, params: PageParams = {}) => ["audit", project ?? "all", params] as const,
  archives: (project: string) => ["archives", project] as const,
};

const base = (project: string) => `${V1}/projects/${project}`;

// Session and account

export const useSystemInfo = () =>
  useQuery({
    queryKey: qk.system,
    queryFn: () => api<SystemInfo>(`${V1}/system/info`),
    staleTime: 60_000,
    retry: false,
  });

export const useMe = (enabled = true) =>
  useQuery({ queryKey: qk.me, queryFn: () => api<User>(`${V1}/auth/me`), enabled, retry: false, staleTime: 60_000 });

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2 };

/** Whether the signed-in person has at least this role (admin > member > viewer). */
export function useCan(minimum: Role): boolean {
  const me = useMe();
  return me.data ? RANK[me.data.role] >= RANK[minimum] : false;
}

export function useLogin(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: (body: { email: string; password: string }) =>
      api<SessionOut>(`${V1}/auth/login`, { method: "POST", json: body }),
    onSuccess: async () => {
      client.clear();
    },
  });
}

export function useSetup(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: (body: { name: string; email: string; password: string }) =>
      api<SessionOut>(`${V1}/auth/setup`, { method: "POST", json: body }),
    onSuccess: async () => {
      client.clear();
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    meta: { silent: true },
    mutationFn: () => api<void>(`${V1}/auth/logout`, { method: "POST" }),
    onSettled: () => client.clear(),
  });
}

export function useChangePassword(options?: HookOptions) {
  return useMutation({
    meta: meta(options),
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api<SessionOut>(`${V1}/auth/password`, { method: "POST", json: body }),
  });
}

export function useUpdateProfile(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: (name: string) => api<User>(`${V1}/auth/me`, { method: "PATCH", json: { name } }),
    onSuccess: (user) => client.setQueryData(qk.me, user),
  });
}

export const useUsers = (enabled = true) =>
  useQuery({ queryKey: qk.users, queryFn: () => api<Page<User>>(`${V1}/users?limit=200`), enabled });

export function useCreateUser(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: (body: { email: string; name: string; role: Role }) =>
      api<UserCreated>(`${V1}/users`, { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.users }),
  });
}

export function useUpdateUser() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; role?: Role; is_active?: boolean }) =>
      api<User>(`${V1}/users/${id}`, { method: "PATCH", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.users }),
  });
}

// Projects

export const useProjects = () =>
  useQuery({ queryKey: qk.projects, queryFn: () => api<Page<Project>>(`${V1}/projects?limit=200`) });

export function useCreateProject(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: (body: { name: string; description: string }) =>
      api<Project>(`${V1}/projects`, { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.projects }),
  });
}

export function useUpdateProject(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: ({ id, ...body }: { id: string } & ProjectUpdate) =>
      api<Project>(`${base(id)}`, { method: "PATCH", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.projects }),
  });
}

export function useDeleteProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(base(id), { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function useTestRedaction() {
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ project, text, redaction }: { project: string; text: string; redaction?: RedactionRules }) =>
      api<RedactionTestResult>(`${base(project)}/redaction/test`, { method: "POST", json: { text, redaction } }),
  });
}

export const useKeys = (project: string | undefined, params: PageParams = {}) =>
  useQuery({
    queryKey: qk.keys(project ?? "", params),
    queryFn: () => api<Page<ProjectKey>>(`${base(project!)}/keys${toQuery({ limit: 100, ...params })}`),
    enabled: Boolean(project),
  });

export function useCreateKey(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: ({ project, name }: { project: string; name: string }) =>
      api<ProjectKeyCreated>(`${base(project)}/keys`, { method: "POST", json: { name } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["keys"] }),
  });
}

export function useRevokeKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ project, id }: { project: string; id: string }) =>
      api<ProjectKey>(`${base(project)}/keys/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["keys"] }),
  });
}

// Traces

export const useTraces = (project: string | undefined, params: TraceParams) =>
  useQuery({
    queryKey: qk.traces(project ?? "", params),
    queryFn: () => api<TracePage>(`${base(project!)}/traces${toQuery(params)}`),
    enabled: Boolean(project),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

export const useTrace = (project: string | undefined, id: string) =>
  useQuery({
    queryKey: qk.trace(project ?? "", id),
    queryFn: () => api<TraceWithSpans>(`${base(project!)}/traces/${encodeURIComponent(id)}`),
    enabled: Boolean(project),
    retry: false,
  });

export const useFacets = (project: string | undefined) =>
  useQuery({
    queryKey: qk.facets(project ?? ""),
    queryFn: () => api<Facets>(`${base(project!)}/traces/facets`),
    enabled: Boolean(project),
    staleTime: 60_000,
  });

// Metrics

export const useOverview = (project: string | undefined, range: string, environment?: string) =>
  useQuery({
    queryKey: qk.overview(project ?? "", range, environment),
    queryFn: () => api<Overview>(`${base(project!)}/metrics/overview${toQuery({ range, environment })}`),
    enabled: Boolean(project),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

export const useBreakdown = (project: string | undefined, dimension: Dimension, range: string) =>
  useQuery({
    queryKey: qk.breakdown(project ?? "", dimension, range),
    queryFn: () => api<Breakdown>(`${base(project!)}/metrics/breakdown${toQuery({ dimension, range })}`),
    enabled: Boolean(project),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

// Prompts

export const usePrompts = (project: string | undefined, range: string, params: PageParams = {}) =>
  useQuery({
    queryKey: qk.prompts(project ?? "", range, params),
    queryFn: () => api<Page<PromptSummary>>(`${base(project!)}/prompts${toQuery({ range, limit: 100, ...params })}`),
    enabled: Boolean(project),
    placeholderData: keepPreviousData,
  });

export const usePrompt = (project: string | undefined, name: string, range: string) =>
  useQuery({
    queryKey: qk.prompt(project ?? "", name, range),
    queryFn: () => api<PromptDetail>(`${base(project!)}/prompts/${name}${toQuery({ range })}`),
    enabled: Boolean(project && name),
    retry: false,
  });

export function useCreatePromptVersion(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: ({
      project,
      ...body
    }: {
      project: string;
      name: string;
      template: string;
      labels: string[];
      commit_message?: string;
    }) => api<PromptVersion>(`${base(project)}/prompts`, { method: "POST", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useMoveLabel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      project,
      name,
      label,
      version,
    }: {
      project: string;
      name: string;
      label: string;
      version: number | null;
    }) => api<{ ok: boolean }>(`${base(project)}/prompts/${name}/label`, { method: "PUT", json: { label, version } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

// Prices

export const usePrices = (project: string | undefined) =>
  useQuery({
    queryKey: qk.prices(project ?? ""),
    queryFn: () => api<Price[]>(`${base(project!)}/prices`),
    enabled: Boolean(project),
  });

export function useUpsertPrice(options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: ({
      project,
      ...body
    }: {
      project: string;
      model: string;
      provider?: string;
      input_per_mtok: string;
      output_per_mtok: string;
      cached_input_per_mtok?: string | null;
    }) => api<Price>(`${base(project)}/prices`, { method: "PUT", json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prices"] }),
  });
}

export function useDeletePrice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ project, id }: { project: string; id: string }) =>
      api<void>(`${base(project)}/prices/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prices"] }),
  });
}

// Budgets and alerts

export const useAlerts = (project: string | undefined) =>
  useQuery({
    queryKey: qk.alerts(project ?? ""),
    queryFn: () => api<AlertsOverview>(`${base(project!)}/alerts`),
    enabled: Boolean(project),
    refetchInterval: 30_000,
  });

export const useAlertEvents = (project: string | undefined, params: PageParams = {}) =>
  useQuery({
    queryKey: qk.alertEvents(project ?? "", params),
    queryFn: () => api<Page<AlertEvent>>(`${base(project!)}/alert-events${toQuery({ limit: 20, ...params })}`),
    enabled: Boolean(project),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

function useAlertWrite<TInput>(run: (input: TInput) => Promise<unknown>, options?: HookOptions) {
  const client = useQueryClient();
  return useMutation({
    meta: meta(options),
    mutationFn: run,
    onSuccess: () => client.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export const useSaveBudget = (options?: HookOptions) =>
  useAlertWrite(
    ({ project, id, body }: { project: string; id?: string; body: BudgetWrite }) =>
      api<Budget>(`${base(project)}/budgets${id ? `/${id}` : ""}`, { method: id ? "PUT" : "POST", json: body }),
    options,
  );

export const useDeleteBudget = () =>
  useAlertWrite(({ project, id }: { project: string; id: string }) =>
    api<void>(`${base(project)}/budgets/${id}`, { method: "DELETE" }),
  );

export const useSaveRule = (options?: HookOptions) =>
  useAlertWrite(
    ({ project, id, body }: { project: string; id?: string; body: RuleWrite }) =>
      api<AlertRule>(`${base(project)}/alert-rules${id ? `/${id}` : ""}`, {
        method: id ? "PUT" : "POST",
        json: body,
      }),
    options,
  );

export const useDeleteRule = () =>
  useAlertWrite(({ project, id }: { project: string; id: string }) =>
    api<void>(`${base(project)}/alert-rules/${id}`, { method: "DELETE" }),
  );

// Audit and archives

export const useAudit = (project: string | undefined, params: PageParams = {}, enabled = true) =>
  useQuery({
    queryKey: qk.audit(project, params),
    queryFn: () => api<Page<AuditEvent>>(`${V1}/audit${toQuery({ project_id: project, limit: 25, ...params })}`),
    enabled,
    placeholderData: keepPreviousData,
  });

export const useArchives = (project: string | undefined, enabled = true) =>
  useQuery({
    queryKey: qk.archives(project ?? ""),
    queryFn: () => api<ArchiveObject[]>(`${base(project!)}/archives`),
    enabled: Boolean(project) && enabled,
  });
