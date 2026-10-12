#!/usr/bin/env bash
# Copy the local SharkSight database into a hosted Postgres (Neon, D-063). Run once from this Mac, BEFORE the Render
# service first starts (or restart it afterwards):
#
#   deploy/render/load-data.sh '<owner connection string from Neon>'     # postgresql://neondb_owner:…/neondb?sslmode=require
#   deploy/render/load-data.sh '<url>' --replace                         # drop everything in the target first
#
# 1. a fresh `make backup`, restored in full (schema, data, then keys / indexes / triggers — in that order, so foreign
#    keys never see half-loaded tables; hosted Postgres has no superuser for --disable-triggers);
# 2. the app role `sharksight_app` + its grants (migrations/sql/0003_app_role.sql) with APP_DB_PASSWORD from the repo's
#    .env — use the same password in Render's DATABASE_URL. The restored alembic_version says the schema is current,
#    so the app's migrations on start have nothing to do.
# Needs the local database running (`make db`); psql / pg_restore run in a throwaway postgres container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
URL="${1:-}"; [[ -n "$URL" ]] || { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
REPLACE=0; [[ "${2:-}" == "--replace" ]] && REPLACE=1
URL="${CONTAINER_URL:-$URL}"   # only for tests against local Postgres: the URL as seen from a container
PG_IMAGE="pgvector/pgvector:0.8.0-pg17"
say() { printf '\033[1m%s\033[0m\n' "$*"; }
psql_url() { docker run --rm -i "$PG_IMAGE" psql "$URL" -v ON_ERROR_STOP=1 -qtA "$@"; }

APP_DB_PASSWORD="$(grep -E '^APP_DB_PASSWORD=' "$ROOT/.env" | tail -1 | cut -d= -f2-)"
[[ -n "$APP_DB_PASSWORD" ]] || { echo "error: APP_DB_PASSWORD missing in .env" >&2; exit 1; }

tables="$(psql_url -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'" | tr -d '[:space:]')"
if [[ "$tables" != "0" ]]; then
  [[ $REPLACE == 1 ]] || { echo "error: the target already has $tables tables — add --replace to drop them" >&2; exit 1; }
  say "dropping everything in the target's public schema…"
  psql_url -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

say "dumping the local database…"
make -C "$ROOT" backup >/dev/null
dump="$(ls -t "$ROOT"/data/backups/sharksight-*.dump | head -1)"
say "restoring $(basename "$dump") ($(du -h "$dump" | cut -f1)) — a few minutes over the internet…"
# --no-owner / --no-privileges: the target's owner owns everything, grants come from 0003 below. The schema-level
# entries (public schema, extension comment) belong to the target already and are left out.
docker run --rm -i -v "$dump:/db.dump:ro" "$PG_IMAGE" sh -c \
  "pg_restore -l /db.dump | grep -v -E ' SCHEMA - public | COMMENT - EXTENSION ' > /tmp/list && \
   pg_restore -d '$URL' --no-owner --no-privileges --single-transaction --exit-on-error -L /tmp/list /db.dump"

say "app role and grants…"
{ cat "$ROOT/backend/migrations/sql/0003_app_role.sql"
  echo "\\set pw '$APP_DB_PASSWORD'"
  echo "ALTER ROLE sharksight_app LOGIN PASSWORD :'pw';"; } | psql_url
psql_url -c "SELECT 'source items: ' || COUNT(*) FROM source_item"
psql_url -c "SELECT 'database size: ' || pg_size_pretty(pg_database_size(current_database()))"
# the app's connection string: the owner URL with the app role's name and password
app_url="$(python3 -c 'import sys, urllib.parse as u; p = u.urlsplit(sys.argv[1]); host = p.netloc.rpartition("@")[2]
print(u.urlunsplit(p._replace(netloc="sharksight_app:" + u.quote(sys.argv[2], safe="") + "@" + host)))' "$1" "$APP_DB_PASSWORD")"
say "done. Render → Environment:"
echo "  DATABASE_URL           = $app_url"
echo "  MIGRATION_DATABASE_URL = (the owner URL you passed in)"
