# Walkthrough: a tour of the demo

`make up && make demo`, then sign in as `admin@example.com`. The demo is two weeks of a customer
copilot: a support agent, a research agent, a SQL analyst, a code reviewer and a summariser pipeline,
six tools, ten models and prompt versions that change as the weeks go by.

1. **Overview.** Cost, tokens, p95 latency and error rate, each against the previous period. The
   cost chart splits spend by model; four days ago the failure chart spikes for two and a half
   hours (GPT-4o timeouts), and nine days ago cost jumps for an afternoon (a research loop).
2. **Traces.** Filter to failures, sort by cost, or search for a user. Open the most expensive
   `research.report`: the waterfall shows the agent, each `web_search` with the summariser model
   call inside it, the slow `fetch_url` calls and the final synthesis. Click a span for tokens,
   cost (and whether it was reported or priced), time to first token and its masked input.
3. **Prompts.** `support-triage` has three versions; v3 is the production label and the chart shows
   it costing about half of v1 per call. Make a different version production and your SDK's next
   `get_prompt` sees it.
4. **Models and pricing.** Where the money goes by model, with latency and error rates. The Pricing
   tab is the table behind every number; add an override for a negotiated rate.
5. **Agents and tools.** Cost per agent (including model calls inside its tools) and per tool, with
   each tool's own latency and failure rate. `run_sql` fails more since `sql-generator` v3.
6. **Budgets and alerts.** The research agent is over its weekly budget; the monthly project budget
   is close. Rules watch error rate, latency and silence; history shows the incident resolved.
7. **API keys.** Create a key and copy the snippet for the SDK, OpenTelemetry or curl.
8. **Settings.** Masking rules with a live tester, sampling, retention with archive-before-delete,
   the alert webhook, people and the activity log.
