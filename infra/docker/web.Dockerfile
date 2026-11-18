# syntax=docker/dockerfile:1.7
# Web app: the Next.js standalone server.
#   docker build -f infra/docker/web.Dockerfile -t tokenprofiler-web .
#
# One image for every environment: the API URL and product name are read at runtime
# (/env.js), never baked in at build time.
ARG NODE_IMAGE=node:22.23.4-bookworm-slim

FROM ${NODE_IMAGE} AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH CI=true NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo

FROM base AS build
# Manifests first: the dependency layer is reused until a manifest or the lockfile changes.
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
# A frozen install checks the lockfile against every workspace member, so the browser-test
# package's manifest has to be here too once that package exists. The bracket makes the
# pattern a glob, which BuildKit allows to match nothing (a literal path would fail the build
# before the package exists, and `e2e` is not part of the image).
COPY e[2]e/package.json e2e/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --filter @tokenprofiler/web...
COPY apps/web apps/web
RUN pnpm --filter @tokenprofiler/web build

FROM ${NODE_IMAGE} AS runtime
LABEL org.opencontainers.image.title="Euron TokenProfiler dashboard" \
      org.opencontainers.image.description="Dashboard for the Euron TokenProfiler registry and gateway" \
      org.opencontainers.image.source="https://github.com/euron-sde-team/euron-token-profiler" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="ENGAGESPHERE TECHNOLOGY PRIVATE LIMITED"
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*
# The standalone trace starts at the repo root, so the server lives at apps/web/server.js.
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/env.js').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "apps/web/server.js"]
