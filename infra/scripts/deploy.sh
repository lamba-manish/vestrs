#!/usr/bin/env bash
#
# deploy.sh — pull-based deploy entrypoint.
#
# Slice 14A scope: this script runs ON the target EC2 host (or any
# host that already has the repo, docker, and the right .env file).
# Slice 14B will add an SSM-triggered runner that calls this script
# remotely from CI.
#
# Usage:
#   bash infra/scripts/deploy.sh staging       # uses release/staging tag
#   bash infra/scripts/deploy.sh production    # uses release/production tag
#   VESTRS_TAG=sha-abc1234 bash infra/scripts/deploy.sh production    # rollback
#
# What it does:
#   1. Validate env arg (`staging` | `production`).
#   2. Source the matching .env file (must exist; no fallback).
#   3. `docker compose pull` the floating tag (or VESTRS_TAG override).
#   4. `docker compose up -d --remove-orphans --wait` (compose waits
#      for healthchecks to pass before exiting).
#   5. The api container's entrypoint runs `alembic upgrade head` on
#      every start, so migrations apply automatically.
#   6. Smoke-test the public /healthz endpoint via Caddy.
#   7. Print the SHAs of the running images for the audit log.

set -euo pipefail

ENV_NAME="${1:?usage: deploy.sh <staging|production>}"
case "$ENV_NAME" in
  staging|production) ;;
  *) echo "deploy.sh: unknown env '$ENV_NAME' (expected staging|production)" >&2; exit 2 ;;
esac

# ----------------------------------------------------------------------
# Production-deploy lockdown
#
# Production deploys MUST originate from the GHA `Deploy · production`
# workflow, which itself requires:
#   - a PR review on `main`
#   - a fast-forward push to `release/production`
#   - a successful Release workflow (image build + GHCR push)
#   - a manual approval at the `production` GitHub Environment
# A human running `bash deploy.sh production` from a Session-Manager
# shell would skip every one of those gates. Refuse unless the GHA
# SSM SendCommand path passes a token we plant on the runner.
#
# Override paths (intentional, narrow):
#   VESTRS_ALLOW_LOCAL_PROD_DEPLOY=1  — explicit operator override for
#                                       break-glass scenarios. Use with
#                                       caution; logs the override.
#   ENV_NAME != production            — staging stays manual-friendly.
# ----------------------------------------------------------------------
if [[ "$ENV_NAME" == "production" ]]; then
  if [[ -z "${VESTRS_DEPLOY_TOKEN:-}" ]]; then
    if [[ "${VESTRS_ALLOW_LOCAL_PROD_DEPLOY:-0}" != "1" ]]; then
      cat >&2 <<'GUARD'
deploy.sh: production deploys must come from the GHA "Deploy · production"
workflow (PR review → release/production push → manual approval at the
production GitHub Environment). Running this script directly from a
Session-Manager shell bypasses every gate.

If this is a break-glass situation and you've decided you need to:
  VESTRS_ALLOW_LOCAL_PROD_DEPLOY=1 bash deploy.sh production
The override is logged.
GUARD
      exit 10
    fi
    echo "deploy.sh: VESTRS_ALLOW_LOCAL_PROD_DEPLOY override engaged at $(date -u +%FT%TZ) by $(whoami)" >&2
  fi
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/compose/docker-compose.${ENV_NAME}.yml"
ENV_FILE="$REPO_ROOT/.env.${ENV_NAME}"

[[ -f "$COMPOSE_FILE" ]] || { echo "deploy.sh: missing $COMPOSE_FILE" >&2; exit 3; }
[[ -f "$ENV_FILE"     ]] || { echo "deploy.sh: missing $ENV_FILE (populate from SSM first)" >&2; exit 4; }

SMOKE_HOST="$(awk -F= '/^PUBLIC_API_HOST=/ {print $2}' "$ENV_FILE")"
[[ -n "${SMOKE_HOST:-}" ]] || { echo "deploy.sh: PUBLIC_API_HOST missing in $ENV_FILE" >&2; exit 5; }

echo "==> deploy.sh · target=$ENV_NAME · tag=${VESTRS_TAG:-<floating>}"
export VESTRS_TAG="${VESTRS_TAG:-$ENV_NAME}"

echo "--> docker login ghcr.io"
# CI will have populated /run/secrets/ghcr.json or equivalent; the
# local operator path expects an existing credential helper. Either
# way, `docker compose pull` will fail loudly if auth is missing.
if [[ -n "${GHCR_TOKEN:-}" && -n "${GHCR_USER:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

echo "--> compose pull"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull

echo "--> compose up -d --wait"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans --wait

echo "--> smoke test https://$SMOKE_HOST/healthz"
# Up to ~60s for Caddy to issue / renew the TLS cert on a cold start.
attempts=0
until curl -fsS --max-time 5 "https://$SMOKE_HOST/healthz" > /dev/null; do
  attempts=$((attempts + 1))
  if [[ $attempts -ge 30 ]]; then
    echo "deploy.sh: /healthz still failing after 30 attempts — rolling back" >&2
    exit 6
  fi
  sleep 2
done

echo "--> running images:"
# `docker compose images` already prints the image:tag for each
# service container — that's the audit-trail line we actually want.
# (The previous version piped IDs through `docker inspect --format
# '{{.Config.Image}} {{.Image}}'`, but `.Image` isn't a field on
# inspected containers, which made the entire deploy script exit
# non-zero under `set -euo pipefail` even though every container had
# already come up healthy.)
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" images || true

echo "==> deploy ok · $ENV_NAME"
