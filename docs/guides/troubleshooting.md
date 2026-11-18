# Troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| `make up` fails with `releases.hashicorp.com: unexpected EOF` | A network flake while the Terraform one-shot downloads providers. Run `make up` again; providers are cached in the `tokenprofiler-tf-plugins` volume. |
| `docker ps` fails | Start Colima (`colima start`) or Docker Desktop. |
| A port is already in use | Set `TP_WEB_PORT`, `TP_API_PORT`, `TP_PG_PORT`, `TP_REDIS_PORT` or `TP_FLOCI_PORT` in `deploy/compose/.env`. |
| The dashboard says it cannot reach the API | `API_URL` in the web container must be the address your browser uses (`http://localhost:8210` locally). |
| Sending traces returns 401 `invalid_api_key` | The key is revoked, mistyped, or you sent a session token. Keys start with `tp_`. |
| Sending traces returns 429 | The key exceeded `INGEST_RATE_LIMIT` requests a minute. Batch more spans per request and honour `Retry-After`. |
| Traces are missing | Sampling may have dropped them (Settings, Sampling), or they are older than retention. Check `rejected` in the ingest response. |
| A model shows cost $0.00 | No price matches its name. Look it up under Models, Pricing and add an override. |
| Tokens show "estimated" | The provider usage was not sent. Pass `usage` (the SDK's `usage_from(response)` reads common clients). |
| Costs look low after a price change | Prices apply to spans ingested afterwards; stored spans keep the price they were billed at. |
| The overview lags behind new traces | Aggregates are cached for 30 seconds (`DASHBOARD_CACHE_TTL_S`). The trace list is not cached. |
| No alert emails or webhooks | Alerts post to the project webhook only. Check Settings, Notifications; a blocked or failing delivery is shown on the event (`notify_error`). The webhook must be a public address. |
| API refuses to start in production | The message lists every unsafe setting (secrets, cookies, CORS, emulator endpoint). |
| Integration tests cannot connect | Run `scripts/test-deps.sh`; they use ports 5461, 6421 and 4621. |
| `make e2e` is rate limited at sign-in | Delete `e2e/.auth` and wait a minute; the suites reuse one session per role. |
