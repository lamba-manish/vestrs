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
FROM base AS builder
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---------- export (deploy script copies /export/dist into the Caddy volume) ----------
FROM scratch AS export
COPY --from=builder /app/dist /dist
