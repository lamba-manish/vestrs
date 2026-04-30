# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS base
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
RUN corepack enable

# ---------- deps ----------
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --prefer-frozen-lockfile || pnpm install

# ---------- dev (used by docker-compose locally) ----------
FROM base AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["pnpm", "dev"]

# ---------- builder (vite -> dist/) ----------
#
# Vite inlines `import.meta.env.VITE_*` at build time, so the API URL
# and app-env label have to be present here, not at runtime. release.yml
# passes them as --build-args based on the target env; the local
# defaults in `apps/web/src/lib/env.ts` cover dev (`pnpm dev`).
FROM base AS builder
WORKDIR /app
ENV NODE_ENV=production
ARG VITE_API_URL
ARG VITE_APP_ENV=production
ENV VITE_API_URL=$VITE_API_URL \
    VITE_APP_ENV=$VITE_APP_ENV
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---------- export (deploy script copies /export/dist into the Caddy volume) ----------
FROM scratch AS export
COPY --from=builder /app/dist /dist
