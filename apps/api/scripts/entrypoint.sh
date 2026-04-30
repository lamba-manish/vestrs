#!/usr/bin/env bash
# API container entrypoint. Per CLAUDE.md sec. 14, every environment runs
# `alembic upgrade head` at container start so schemas can never drift.

set -euo pipefail

echo "[entrypoint] applying migrations…"
alembic upgrade head

echo "[entrypoint] starting uvicorn…"
exec uvicorn app.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --no-access-log \
    --proxy-headers \
    --forwarded-allow-ips="*"
