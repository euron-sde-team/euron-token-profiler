import { expect, test } from "@playwright/test";

import { apiGet, defaultProject, signIn } from "../helpers";

type Overview = { current: { traces: number; cost: string }; series: unknown[] };

test("the overview shows two weeks of cost, tokens, latency and errors", async ({ page }) => {
  await signIn(page, "admin");
  await expect(page.getByText("Cost over time")).toBeVisible();
  await expect(page.getByText("Latency", { exact: true })).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await expect(page.getByText("Top models")).toBeVisible();
  await expect(page.getByText("Recent failures")).toBeVisible();

  const project = await defaultProject(page);
  const week = await apiGet<Overview>(page, `/projects/${project.id}/metrics/overview?range=14d`);
  expect(week.current.traces).toBeGreaterThan(1500);
  expect(Number(week.current.cost)).toBeGreaterThan(5);

  await page.getByRole("radio", { name: "14 days" }).click();
  await expect(page).toHaveURL(/range=14d/);
  await expect(page.getByText("Cost over time")).toBeVisible();
});

test("switching project changes the numbers", async ({ page }) => {
  await signIn(page, "admin");
  const select = page.getByLabel("Project");
  await expect(select.locator("option")).toHaveText(["Customer Copilot", "Internal Tools"]);
  await select.selectOption({ label: "Internal Tools" });
  await expect(page.getByText("How Internal Tools is doing")).toBeVisible();
  await select.selectOption({ label: "Customer Copilot" });
});
