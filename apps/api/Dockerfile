# syntax=docker/dockerfile:1.7

# ---------- base (no uv — keeps the runtime image small + CVE-clean) ----------
FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ---------- builder (adds uv only here) ----------
FROM base AS builder
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.5.6 /uv /uvx /usr/local/bin/
WORKDIR /app

# Install dependencies first (cached) — copy lockfile if present.
COPY pyproject.toml ./
COPY uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# Copy app source and finalize venv.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ---------- runtime (no uv — Trivy cleanly skips Go-stdlib CVEs in uv) ----------
FROM base AS runtime
WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts

RUN chmod +x /app/scripts/entrypoint.sh

ENV PATH="/app/.venv/bin:${PATH}"
USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
