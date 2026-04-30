#!/usr/bin/env bash
#
# Pulls a dump from S3 (or a local file) and restores it into the
# matching env's postgres container. Use this in DR drills + actual
# DR — the restore always goes into the live container, replacing
# whatever's there. Confirmation prompt prevents foot-guns.
#
# Usage:
#   bash infra/scripts/restore-postgres.sh staging s3://vestrs-staging-pgbackups/staging/2026-04-30T031700Z.sql.gz
#   bash infra/scripts/restore-postgres.sh production /tmp/dump.sql.gz

set -euo pipefail

ENV_NAME="${1:?usage: restore-postgres.sh <staging|production> <s3://... | path>}"
SOURCE="${2:?usage: restore-postgres.sh <env> <s3://... | path>}"
case "$ENV_NAME" in staging|production) ;; *) echo "unknown env: $ENV_NAME" >&2; exit 2 ;; esac

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/compose/docker-compose.${ENV_NAME}.yml"
ENV_FILE="$REPO_ROOT/.env.${ENV_NAME}"

[[ -f "$COMPOSE_FILE" ]] || { echo "missing $COMPOSE_FILE" >&2; exit 3; }
[[ -f "$ENV_FILE"     ]] || { echo "missing $ENV_FILE"     >&2; exit 4; }

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}"

echo "RESTORE TARGET:"
echo "  env:  $ENV_NAME"
echo "  db:   $POSTGRES_DB"
echo "  from: $SOURCE"
echo
echo "This will DROP and recreate \`$POSTGRES_DB\`, replacing all data."
read -rp "Type the env name to confirm: " ACK
[[ "$ACK" == "$ENV_NAME" ]] || { echo "aborted"; exit 5; }

TMP="$(mktemp -d)"
DUMP="$TMP/restore.sql.gz"

if [[ "$SOURCE" == s3://* ]]; then
  echo "==> aws s3 cp $SOURCE → $DUMP"
  aws s3 cp "$SOURCE" "$DUMP"
else
  cp "$SOURCE" "$DUMP"
fi

echo "==> dropping + recreating $POSTGRES_DB"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\";"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$POSTGRES_DB\";"

echo "==> piping dump into psql"
gunzip -c "$DUMP" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "==> alembic upgrade head (idempotent)"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  alembic upgrade head

rm -rf "$TMP"
echo "==> restore ok"
