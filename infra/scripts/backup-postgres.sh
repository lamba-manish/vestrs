#!/usr/bin/env bash
#
# Local-side wrapper around pg_dump for ad-hoc backups. The production
# nightly path runs the inline systemd unit installed by cloud-init
# (/usr/local/bin/vestrs-pgbackup); this script is what an operator
# runs manually from /opt/vestrs to grab an extra snapshot.
#
# Usage (on the EC2 host):
#   bash infra/scripts/backup-postgres.sh staging
#   bash infra/scripts/backup-postgres.sh production [--no-s3]

set -euo pipefail

ENV_NAME="${1:?usage: backup-postgres.sh <staging|production> [--no-s3]}"
case "$ENV_NAME" in staging|production) ;; *) echo "unknown env: $ENV_NAME" >&2; exit 2 ;; esac
NO_S3=0
if [[ "${2:-}" == "--no-s3" ]]; then NO_S3=1; fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/compose/docker-compose.${ENV_NAME}.yml"
ENV_FILE="$REPO_ROOT/.env.${ENV_NAME}"

[[ -f "$COMPOSE_FILE" ]] || { echo "missing $COMPOSE_FILE" >&2; exit 3; }
[[ -f "$ENV_FILE"     ]] || { echo "missing $ENV_FILE"     >&2; exit 4; }

# shellcheck disable=SC1090
source "$ENV_FILE"
: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}"

TS="$(date -u +%FT%H%M%SZ)"
TMP="$(mktemp -d)"
DUMP="$TMP/${ENV_NAME}-${TS}.sql.gz"

echo "==> pg_dump → $DUMP"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip -9 > "$DUMP"

echo "==> dump size: $(du -h "$DUMP" | awk '{print $1}')"

if [[ "$NO_S3" -eq 0 ]]; then
  BUCKET="vestrs-${ENV_NAME}-pgbackups"
  KEY="${ENV_NAME}/manual/${TS}.sql.gz"
  echo "==> uploading to s3://$BUCKET/$KEY"
  aws s3 cp "$DUMP" "s3://$BUCKET/$KEY" --storage-class STANDARD_IA
  rm -rf "$TMP"
  echo "==> ok: s3://$BUCKET/$KEY"
else
  echo "==> --no-s3 set; dump is at $DUMP (not cleaned up)"
fi
