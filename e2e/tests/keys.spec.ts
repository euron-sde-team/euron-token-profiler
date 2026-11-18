import { expect, test } from "@playwright/test";

import { API_URL, signIn, unique } from "../helpers";

test("create a key, send a trace with it, find it in the app, then revoke the key", async ({ page, request }) => {
  const name = unique("e2e-key");
  await signIn(page, "member");
  await page.goto("/keys");
  await page.getByRole("button", { name: "Create key" }).first().click();
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create key" }).last().click();
  const key = (await page.getByRole("dialog").getByLabel("API key", { exact: true }).textContent())?.trim() ?? "";
  expect(key).toMatch(/^tp_/);
  await page.getByRole("button", { name: "Done" }).click();

  const traceId = `e2e${Date.now().toString(16)}`.padEnd(32, "0");
  const now = new Date().toISOString();
  const headers = { authorization: `Bearer ${key}`, "content-type": "application/json" };
  const sent = await request.post(`${API_URL}/v1/ingest`, {
    headers,
    data: {
      traces: [{ id: traceId, name: `e2e ${name}`, user_id: "e2e-user" }],
      spans: [
        {
          id: "a1",
          trace_id: traceId,
          name: "e2e-agent",
          kind: "agent",
          start_time: now,
          end_time: new Date(Date.now() + 1500).toISOString(),
        },
        {
          id: "g1",
          trace_id: traceId,
          parent_id: "a1",
          name: "reply",
          kind: "generation",
          start_time: now,
          model: "gpt-4o",
          usage: { input: 2000, output: 300 },
          input: "my email is e2e.person@example.com",
          output: "ok",
        },
      ],
    },
  });
  expect(sent.status()).toBe(200);
  expect((await sent.json()).accepted_spans).toBe(2);

  await page.goto(`/traces?range=1h&q=${traceId.slice(0, 12)}`);
  await page
    .getByRole("region", { name: "Traces" })
    .getByRole("link", { name: `e2e ${name}` })
    .click();
  await expect(page.getByRole("list", { name: "Spans" }).getByText("e2e-agent")).toBeVisible();
  await page.getByRole("list", { name: "Spans" }).getByRole("button", { name: /reply/ }).click();
  await expect(page.getByText("[REDACTED:email]").first()).toBeVisible();
  await expect(page.getByText("e2e.person@example.com")).toHaveCount(0);

  await page.goto("/keys");
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row.getByText("Active")).toBeVisible();
  await row.getByRole("button", { name: `Revoke ${name}` }).click();
  await page.getByRole("button", { name: "Revoke", exact: true }).click();
  await expect(row.getByText("Revoked")).toBeVisible();
  const revoked = await request.post(`${API_URL}/v1/ingest`, { headers, data: {} });
  expect(revoked.status()).toBe(401);
});

test("an OpenTelemetry exporter can send with the same key", async ({ page, request }) => {
  await signIn(page, "member");
  await page.goto("/keys");
  const name = unique("otlp-key");
  await page.getByRole("button", { name: "Create key" }).first().click();
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create key" }).last().click();
  const key = (await page.getByRole("dialog").getByLabel("API key", { exact: true }).textContent())?.trim() ?? "";
  await page.getByRole("button", { name: "Done" }).click();

  const nanos = BigInt(Date.now()) * 1_000_000n;
  const trace = "ab".repeat(16);
  const response = await request.post(`${API_URL}/v1/otlp/v1/traces`, {
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    data: {
      resourceSpans: [
        {
          resource: { attributes: [{ key: "service.name", value: { stringValue: "otel-demo" } }] },
          scopeSpans: [
            {
              spans: [
                {
                  traceId: trace,
                  spanId: "00000000000000f1",
                  name: "chat",
                  startTimeUnixNano: nanos.toString(),
                  endTimeUnixNano: (nanos + 800_000_000n).toString(),
                  attributes: [
                    { key: "gen_ai.operation.name", value: { stringValue: "chat" } },
                    { key: "gen_ai.request.model", value: { stringValue: "claude-sonnet-4-5" } },
                    { key: "gen_ai.usage.input_tokens", value: { intValue: "1200" } },
                    { key: "gen_ai.usage.output_tokens", value: { intValue: "90" } },
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  });
  expect(response.status()).toBe(200);
  await page.goto(`/traces?range=1h&model=claude-sonnet-4-5&q=${trace.slice(0, 8)}`);
  await expect(page.getByRole("region", { name: "Traces" }).getByRole("link", { name: "chat" })).toBeVisible();
});
