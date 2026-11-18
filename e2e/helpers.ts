import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const API_URL = process.env.API_URL ?? "http://localhost:8210";
export const WEB_URL = process.env.WEB_URL ?? "http://localhost:3210";
export const PASSWORD = process.env.DEMO_PASSWORD ?? "";

/** The people `make demo` creates: an administrator, a member and a viewer. */
export const PEOPLE = {
  admin: { email: "admin@example.com", name: "Ada Admin" },
  member: { email: "maya@example.com", name: "Maya Chen" },
  viewer: { email: "viewer@example.com", name: "Victor Reyes" },
} as const;

export type Person = keyof typeof PEOPLE;

export function requirePassword(): string {
  if (!PASSWORD) throw new Error("Set DEMO_PASSWORD (make e2e reads it from deploy/compose/.env)");
  return PASSWORD;
}

const SESSIONS = path.resolve(__dirname, ".auth");

/** Sign in through the form, exactly as a person does. */
export async function signInWithForm(page: Page, who: Person = "admin"): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(PEOPLE[who].email);
  await page.getByLabel("Password").fill(requirePassword());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
}

/**
 * A signed-in page for one demo person. The session cookie from the first form sign-in is
 * saved per role and reused by later tests: the API allows ten sign-ins a minute per
 * address, and the suites would otherwise trip that limit themselves. A stale cookie (after
 * `make down`) falls back to the form.
 */
export async function signIn(page: Page, who: Person = "admin"): Promise<void> {
  const saved = path.join(SESSIONS, `${who}.json`);
  if (existsSync(saved)) {
    await page.context().addCookies(JSON.parse(readFileSync(saved, "utf8")));
    // Ask the API, not the page: a stale cookie only shows as a redirect after the page loads.
    const session = await page.request.get(`${API_URL}/api/v1/auth/me`);
    if (session.ok()) {
      await page.goto("/overview");
      return;
    }
    await page.context().clearCookies();
  }
  await signInWithForm(page, who);
  mkdirSync(SESSIONS, { recursive: true });
  writeFileSync(saved, JSON.stringify(await page.context().cookies()));
}

export type ApiProject = { id: string; slug: string; name: string };

/** The project the app opens on: the oldest, which is "Customer Copilot" in the demo. */
export async function defaultProject(page: Page): Promise<ApiProject> {
  const projects = await apiGet<{ items: ApiProject[] }>(page, "/projects");
  return projects.items[0]!;
}

/** GET an API path with the page's session; returns the parsed body. */
export async function apiGet<T>(page: Page, apiPath: string): Promise<T> {
  const response = await page.request.get(`${API_URL}/api/v1${apiPath}`);
  expect(response.ok(), apiPath).toBeTruthy();
  return (await response.json()) as T;
}

/**
 * Send a request to the API as the signed-in person. Unsafe methods must come from the
 * web app's own origin (the API's CSRF check), so the origin header is set the way the
 * browser would set it.
 */
export async function apiSend<T>(
  page: Page,
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  apiPath: string,
  data?: unknown,
): Promise<T> {
  const response = await page.request.fetch(`${API_URL}/api/v1${apiPath}`, {
    method,
    data,
    headers: { origin: WEB_URL },
  });
  expect(response.ok(), `${method} ${apiPath}: ${await response.text()}`).toBeTruthy();
  return (response.status() === 204 ? undefined : await response.json()) as T;
}

/** A name for throwaway data that no other run or demo person shares. */
export function unique(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

/** Wait until the page has settled: no pending network, fonts ready, transitions finished. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    await document.fonts.ready;
    // Spinners and pulsing dots repeat forever; only wait for animations that end.
    const finite = document
      .getAnimations()
      .filter((animation) => animation.effect?.getTiming().iterations !== Infinity);
    await Promise.all(finite.map((animation) => animation.finished.catch(() => undefined)));
  });
}
