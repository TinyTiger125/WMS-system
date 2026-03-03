#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ODOO_CONF="${ODOO_CONF:-$ROOT_DIR/odoo.conf}"
BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" ]]; then
  echo "Usage: $0 /path/to/backup.dump"
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

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

resolve_pg_restore() {
  if command -v pg_restore >/dev/null 2>&1; then
    command -v pg_restore
    return
  fi
  local candidates=(
    "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_restore"
    "/opt/homebrew/opt/postgresql@16/bin/pg_restore"
    "/usr/local/opt/postgresql@16/bin/pg_restore"
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

PG_RESTORE_BIN="$(resolve_pg_restore || true)"
if [[ -z "$PG_RESTORE_BIN" ]]; then
  echo "pg_restore not found. Install PostgreSQL client tools or add pg_restore to PATH."
  exit 1
fi

export PGPASSWORD="$DB_PASSWORD"
"$PG_RESTORE_BIN" \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --clean \
  --if-exists \
  "$BACKUP_FILE"
unset PGPASSWORD

echo "Restore complete from: $BACKUP_FILE"
