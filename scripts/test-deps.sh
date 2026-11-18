#!/usr/bin/env bash
# Make sure the services the integration tests need are reachable: Postgres, Valkey and
# Floci, from the compose stack (started on their own if the stack is down). The suite
# creates its own `tokenprofiler_test` database, uses Valkey database 15 and makes
# uniquely named buckets, so the development data is never touched.
#
#   scripts/test-deps.sh          start (or reuse) the three services
#   scripts/test-deps.sh stop     stop them again (keeps their volumes)
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml
  -f deploy/compose/compose.floci.yaml)
[[ -f deploy/compose/.env ]] || scripts/gen-local-env.sh >/dev/null
if [[ "${1:-}" == "stop" ]]; then
  "${compose[@]}" stop postgres valkey floci
  exit 0
fi
"${compose[@]}" up -d --wait postgres valkey floci >/dev/null
echo "test services ready: postgres :${TP_PG_PORT:-5461}, valkey :${TP_REDIS_PORT:-6421}, floci :${TP_FLOCI_PORT:-4621}"
