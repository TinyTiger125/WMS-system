#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="$ROOT_DIR/scripts/backup_odoo_db.sh"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
ODOO_CONF="${ODOO_CONF:-$ROOT_DIR/odoo.conf}"

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

if [[ ! -x "$BACKUP_SCRIPT" ]]; then
  echo "Backup script not executable: $BACKUP_SCRIPT"
  exit 1
fi

echo "[1/3] Running backup..."
"$BACKUP_SCRIPT"

latest_dump="$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | head -n 1 || true)"
if [[ -z "$latest_dump" ]]; then
  echo "No backup dump found in $BACKUP_DIR"
  exit 1
fi
echo "[2/3] Latest backup: $latest_dump"

PG_RESTORE_BIN="$(resolve_pg_restore || true)"
if [[ -z "$PG_RESTORE_BIN" ]]; then
  echo "[3/3] pg_restore not found, skip archive validation."
  exit 0
fi

echo "[3/3] Validating dump archive format..."
"$PG_RESTORE_BIN" -l "$latest_dump" >/dev/null
echo "Backup validation passed."
