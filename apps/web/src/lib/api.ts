import { runtimeEnv } from "@/lib/runtime-env";

/** A failed API call, carrying the server's error envelope. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string | null = null,
    readonly details: unknown = undefined,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** The browser could not reach the API at all (down, blocked, or a wrong API_URL). */
  get isNetwork(): boolean {
    return this.status === 0;
  }
}

type Envelope = {
  error?: { code?: string; message?: string; request_id?: string; details?: unknown };
};

/** Build an ApiError from a status and the parsed body (the server's error envelope). */
export function errorFrom(status: number, body: unknown, headerRequestId?: string | null): ApiError {
  const error = (body as Envelope | null)?.error;
  return new ApiError(
    status,
    error?.code ?? (status >= 500 ? "server_error" : "request_failed"),
    error?.message ?? "The request failed. Try again.",
    error?.request_id ?? headerRequestId ?? null,
    error?.details,
  );
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export function apiUrl(path: string): string {
  return `${runtimeEnv().apiUrl}${path}`;
}

/**
 * JSON over fetch with the session cookie; throws ApiError on any non-2xx response.
 * Nothing is retried here: a retried write (a secret, a key) could be applied twice.
 */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, headers, ...rest } = options;
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      credentials: "include",
      ...rest,
      headers: {
        accept: "application/json",
        ...(json !== undefined ? { "content-type": "application/json" } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the TokenProfiler API. Is it running?");
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) throw errorFrom(response.status, body, response.headers.get("x-request-id"));
  return body as T;
}

export type QueryValue = string | number | boolean | null | undefined | readonly string[];

/**
 * A query string from an object: arrays repeat the key (`status=ok&status=denied`), and null,
 * undefined and empty values are left out, so call sites can pass raw filter state. Returns
 * "" or a string starting with "?".
 */
export function toQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, item);
    } else {
      search.append(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const V1 = "/api/v1";
