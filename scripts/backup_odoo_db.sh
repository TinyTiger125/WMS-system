#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ODOO_CONF="${ODOO_CONF:-$ROOT_DIR/odoo.conf}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

conf_get() {
  local key="$1"
  awk -F'=' -v key="$key" '
    $1 ~ "^[[:space:]]*"key"[[:space:]]*$" {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2);
      print $2;
      exit;
    }
  ' "$ODOO_CONF"
}

resolve_pg_dump() {
  if command -v pg_dump >/dev/null 2>&1; then
    command -v pg_dump
    return
  fi
  local candidates=(
    "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump"
    "/opt/homebrew/opt/postgresql@16/bin/pg_dump"
    "/usr/local/opt/postgresql@16/bin/pg_dump"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
  return 1
}

if [[ ! -f "$ODOO_CONF" ]]; then
  echo "Missing odoo config: $ODOO_CONF"
  exit 1
fi

DB_HOST="$(conf_get db_host)"
DB_PORT="$(conf_get db_port)"
DB_USER="$(conf_get db_user)"
DB_PASSWORD="$(conf_get db_password)"
DB_NAME="$(conf_get db_name)"

if [[ -z "$DB_NAME" ]]; then
  echo "db_name is empty in $ODOO_CONF"
  exit 1
fi

PG_DUMP_BIN="$(resolve_pg_dump || true)"
if [[ -z "$PG_DUMP_BIN" ]]; then
  echo "pg_dump not found. Install PostgreSQL client tools or add pg_dump to PATH."
  exit 1
fi

mkdir -p "$BACKUP_DIR"
ts="$(date +%Y%m%d_%H%M%S)"
backup_file="$BACKUP_DIR/${DB_NAME}_${ts}.dump"

export PGPASSWORD="$DB_PASSWORD"
"$PG_DUMP_BIN" \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "$DB_USER" \
  -Fc "$DB_NAME" \
  -f "$backup_file"
unset PGPASSWORD

find "$BACKUP_DIR" -type f -name "${DB_NAME}_*.dump" -mtime +"$RETENTION_DAYS" -delete

echo "Backup complete: $backup_file"
