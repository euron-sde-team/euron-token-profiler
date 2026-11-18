import { expect, test } from "@playwright/test";

import { API_URL, signIn, unique } from "../helpers";

test("prompts show their versions, usage and what each version cost", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/prompts");
  const table = page.getByRole("region", { name: "Prompts" });
  await expect(table.getByRole("link", { name: "support-triage" })).toBeVisible();
  await expect(table.getByText("production").first()).toBeVisible();
  await table.getByRole("link", { name: "support-triage" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "support-triage" })).toBeVisible();
  const versions = page.getByRole("region", { name: "Prompt versions" });
  await expect(versions.getByRole("row")).toHaveCount(4);
  await expect(page.getByText("Cost per 1,000 calls by version")).toBeVisible();
  await expect(
    page.getByRole("region", { name: /Template of version 3/ }).or(page.getByLabel("Template of version 3")),
  ).toBeVisible();
});

test("a member saves a new prompt, promotes a version and an SDK can fetch it", async ({ page, request }) => {
  const name = unique("e2e-prompt");
  await signIn(page, "member");
  await page.goto("/prompts");
  await page.getByRole("button", { name: "New prompt" }).first().click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Template").fill("Answer briefly: {{question}}");
  await page.getByLabel("Labels").fill("production");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  await page.getByRole("button", { name: "New version" }).click();
  await page.getByLabel("Template").fill("Answer briefly and cite sources: {{question}}");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByRole("region", { name: "Prompt versions" }).getByRole("row")).toHaveCount(3);
  await page.getByRole("button", { name: "Make production" }).click();
  await expect(page.getByRole("row", { name: /v2/ }).getByText("production")).toBeVisible();

  // The project key of the demo is not known to the test; create one through the API as the member.
  const projects = await page.request.get(`${API_URL}/api/v1/projects`);
  const project = (await projects.json()).items[0];
  const made = await page.request.post(`${API_URL}/api/v1/projects/${project.id}/keys`, {
    data: { name: unique("fetch") },
    headers: { origin: "http://localhost:3210" },
  });
  const key = (await made.json()).key;
  const fetched = await request.get(`${API_URL}/v1/prompts/${name}`, { headers: { authorization: `Bearer ${key}` } });
  expect(fetched.status()).toBe(200);
  const body = await fetched.json();
  expect(body.version).toBe(2);
  expect(body.template).toContain("cite sources");
});
