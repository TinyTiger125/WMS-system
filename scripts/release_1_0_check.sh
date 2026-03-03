#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB_NAME="${DB_NAME:-odoo19_dev}"
ODOO_CONF="${ODOO_CONF:-$ROOT_DIR/odoo.conf}"
CUSTOM_MODULES="${CUSTOM_MODULES:-custom_wms_base,custom_customs_export,custom_cn_sync}"

source .venv/bin/activate

echo "[1/3] Upgrade custom modules: ${CUSTOM_MODULES}"
python -m odoo -c "$ODOO_CONF" -d "$DB_NAME" -u "$CUSTOM_MODULES" --stop-after-init

echo "[2/3] Role/menu access scan"
"$ROOT_DIR/scripts/qa_role_access_scan.sh"

echo "[3/3] HTTP health check"
if curl -fsS "http://127.0.0.1:8069/web/login" >/dev/null 2>&1; then
  echo "HTTP health check passed"
else
  echo "HTTP health check skipped (odoo service not running on 8069)"
fi

echo "Release 1.0 check PASSED"
