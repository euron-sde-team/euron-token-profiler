import { expect, test } from "@playwright/test";

import { signIn, unique } from "../helpers";

test("budgets show spend against limits and alert history", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/budgets");
  await expect(page.getByRole("heading", { level: 1, name: "Budgets and alerts" })).toBeVisible();
  await expect(page.getByRole("progressbar").first()).toBeVisible();
  await expect(page.getByText("Research agent, weekly")).toBeVisible();
  await expect(page.getByRole("region", { name: "Alert rules" }).getByRole("row")).not.toHaveCount(1);
  await expect(page.getByRole("region", { name: "Alert history" })).toBeVisible();
});

test("a member creates a budget and a rule, then removes them", async ({ page }) => {
  const budget = unique("e2e-budget");
  const rule = unique("e2e-rule");
  await signIn(page, "member");
  await page.goto("/budgets");

  await page.getByRole("button", { name: "New budget" }).click();
  await page.getByLabel("Name").fill(budget);
  await page.getByLabel("Applies to").selectOption("model");
  await page.getByLabel("Model", { exact: true }).selectOption({ index: 1 });
  await page.getByLabel("Limit, USD").fill("250");
  await page.getByRole("button", { name: "Create budget" }).click();
  await expect(page.getByText(budget)).toBeVisible();

  await page.getByRole("button", { name: "New rule" }).click();
  await page.getByLabel("Name").fill(rule);
  await page.getByLabel("Threshold (%)").fill("12");
  await page.getByRole("button", { name: "Create rule" }).click();
  await expect(page.getByRole("row", { name: new RegExp(rule) })).toBeVisible();

  await page.getByRole("button", { name: `Delete ${rule}` }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByRole("row", { name: new RegExp(rule) })).toHaveCount(0);
  await page.getByRole("button", { name: `Delete ${budget}` }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText(budget)).toHaveCount(0);
});
