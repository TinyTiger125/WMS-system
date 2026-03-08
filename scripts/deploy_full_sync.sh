#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_SCRIPT="$ROOT_DIR/scripts/build_installer_bundle.sh"
VERIFY_SCRIPT="$ROOT_DIR/scripts/verify_remote_consistency.sh"

REMOTE_USER=""
REMOTE_HOST=""
REMOTE_DIR="/home/neo/WMS-system"
VERSION="1.0.0"
ODOO_CONF="$ROOT_DIR/odoo.conf"
SSH_PASSWORD="${WMS_SSH_PASSWORD:-}"
ASSUME_YES="false"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/deploy_full_sync.sh --user neo --host 100.122.169.32 [options]

Options:
  --user <name>          SSH user (required)
  --host <ip_or_domain>  SSH host (required)
  --remote-dir <path>    Remote project path (default: /home/neo/WMS-system)
  --version <x.y.z>      Bundle version tag (default: 1.0.0)
  --odoo-conf <path>     Local odoo.conf path (default: ./odoo.conf)
  --password <text>      SSH password (optional; can also use env WMS_SSH_PASSWORD)
  --yes                  Skip destructive confirmation

Notes:
  1) This command REPLACES remote DB content with local DB dump.
  2) Recommended to use SSH key auth. Password mode requires `expect`.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) REMOTE_USER="$2"; shift 2 ;;
    --host) REMOTE_HOST="$2"; shift 2 ;;
    --remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --odoo-conf) ODOO_CONF="$2"; shift 2 ;;
    --password) SSH_PASSWORD="$2"; shift 2 ;;
    --yes) ASSUME_YES="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

[[ -n "$REMOTE_USER" ]] || { echo "Missing --user"; usage; exit 1; }
[[ -n "$REMOTE_HOST" ]] || { echo "Missing --host"; usage; exit 1; }
[[ -f "$ODOO_CONF" ]] || { echo "odoo.conf not found: $ODOO_CONF"; exit 1; }
[[ -x "$BUILD_SCRIPT" ]] || { echo "Missing build script: $BUILD_SCRIPT"; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }; }
need_cmd awk
need_cmd tar
need_cmd scp
need_cmd ssh

if [[ -n "$SSH_PASSWORD" ]]; then
  need_cmd expect
fi

conf_get() {
  local key="$1"
  awk -F'=' -v key="$key" '
    $1 ~ "^[[:space:]]*" key "[[:space:]]*$" {
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

ssh_run() {
  local remote_cmd="$1"
  if [[ -n "$SSH_PASSWORD" ]]; then
    expect <<EOF
set timeout -1
spawn ssh ${REMOTE_USER}@${REMOTE_HOST} {${remote_cmd}}
expect {
  "*yes/no*" { send "yes\r"; exp_continue }
  "*password:*" { send "${SSH_PASSWORD}\r" }
}
expect eof
EOF
  else
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "${remote_cmd}"
  fi
}

scp_put() {
  local local_file="$1"
  local remote_path="$2"
  if [[ -n "$SSH_PASSWORD" ]]; then
    expect <<EOF
set timeout -1
spawn scp ${local_file} ${REMOTE_USER}@${REMOTE_HOST}:${remote_path}
expect {
  "*yes/no*" { send "yes\r"; exp_continue }
  "*password:*" { send "${SSH_PASSWORD}\r" }
}
expect eof
EOF
  else
    scp "${local_file}" "${REMOTE_USER}@${REMOTE_HOST}:${remote_path}"
  fi
}

if [[ "$ASSUME_YES" != "true" ]]; then
  echo "WARNING: this will overwrite remote DB with LOCAL DB data."
  echo "Target: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
  read -r -p "Type YES to continue: " answer
  [[ "$answer" == "YES" ]] || { echo "Aborted."; exit 1; }
fi

DB_HOST="$(conf_get db_host)"
DB_PORT="$(conf_get db_port)"
DB_USER="$(conf_get db_user)"
DB_PASSWORD="$(conf_get db_password)"
DB_NAME="$(conf_get db_name)"

[[ -n "$DB_NAME" ]] || { echo "db_name missing in $ODOO_CONF"; exit 1; }
[[ -n "$DB_USER" ]] || { echo "db_user missing in $ODOO_CONF"; exit 1; }

PG_DUMP_BIN="$(resolve_pg_dump || true)"
[[ -n "$PG_DUMP_BIN" ]] || { echo "pg_dump not found"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
TMP_DIR="$ROOT_DIR/dist/fullsync_${TS}"
mkdir -p "$TMP_DIR"
LOCAL_DUMP="$TMP_DIR/local_${DB_NAME}_${TS}.dump"

echo "[1/7] Build installer bundle"
"$BUILD_SCRIPT" "$VERSION"
BUNDLE="$ROOT_DIR/dist/custom-wms-installer-${VERSION}.tar.gz"
[[ -f "$BUNDLE" ]] || { echo "Bundle missing: $BUNDLE"; exit 1; }

echo "[2/7] Dump local DB: $DB_NAME"
export PGPASSWORD="${DB_PASSWORD:-}"
"$PG_DUMP_BIN" \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "$DB_USER" \
  -Fc "$DB_NAME" \
  -f "$LOCAL_DUMP"
unset PGPASSWORD

echo "[3/7] Upload bundle + DB dump"
scp_put "$BUNDLE" "~/custom-wms-installer-${VERSION}.tar.gz"
scp_put "$LOCAL_DUMP" "~/local_${DB_NAME}_${TS}.dump"

echo "[4/7] Sync code to remote project directory"
ssh_run "set -e; cd ~; rm -rf custom-wms-installer-${VERSION}; tar -xzf custom-wms-installer-${VERSION}.tar.gz; rsync -a --delete --exclude 'deploy/.env' ~/custom-wms-installer-${VERSION}/ ${REMOTE_DIR}/"

echo "[5/7] Restore local DB dump to remote DB"
ssh_run "set -e; cd ${REMOTE_DIR}; DB_PASS=\$(grep '^POSTGRES_PASSWORD=' deploy/.env | cut -d= -f2-); DB_USER=\$(grep '^POSTGRES_USER=' deploy/.env | cut -d= -f2-); DB_NAME=\$(grep '^POSTGRES_DB=' deploy/.env | cut -d= -f2-); docker compose -f deploy/compose.yaml --env-file deploy/.env up -d db; until docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' wms_db 2>/dev/null | grep -q healthy; do sleep 2; done; docker exec -i -e PGPASSWORD=\$DB_PASS wms_db pg_restore -U \$DB_USER -d \$DB_NAME --clean --if-exists < ~/local_${DB_NAME}_${TS}.dump"

echo "[6/7] Reinstall/upgrade app from synced code"
ssh_run "set -e; cd ${REMOTE_DIR}; ./INSTALL.sh"

echo "[7/7] Verify remote service"
ssh_run "set -e; cd ${REMOTE_DIR}; ./installer/status.sh; echo HTTP=\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8069/web/login)"

if [[ -x "$VERIFY_SCRIPT" ]]; then
  echo "[post-check] Verify local/remote/container consistency"
  verify_args=(--user "$REMOTE_USER" --host "$REMOTE_HOST" --remote-dir "$REMOTE_DIR")
  if [[ -n "$SSH_PASSWORD" ]]; then
    verify_args+=(--password "$SSH_PASSWORD")
  fi
  "$VERIFY_SCRIPT" "${verify_args[@]}"
fi

echo "Done. Full sync deployment completed."
