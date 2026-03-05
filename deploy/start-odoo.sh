#!/usr/bin/env bash
set -euo pipefail

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=odoo}"
: "${DB_PASSWORD:=odoo}"
: "${ODOO_DB_NAME:=odoo19_prod}"
: "${ODOO_ADMIN_PASSWD:=admin}"
: "${ODOO_HTTP_PORT:=8069}"
: "${ODOO_ADDONS_PATH:=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons}"
: "${ODOO_DATA_DIR:=/var/lib/odoo}"
: "${ODOO_LOGFILE:=/var/log/odoo/odoo.log}"
: "${ODOO_PROXY_MODE:=False}"

args=(
  --db_host="${DB_HOST}"
  --db_port="${DB_PORT}"
  --db_user="${DB_USER}"
  --db_password="${DB_PASSWORD}"
  -d "${ODOO_DB_NAME}"
  --http-port="${ODOO_HTTP_PORT}"
  --addons-path="${ODOO_ADDONS_PATH}"
  --data-dir="${ODOO_DATA_DIR}"
  --logfile="${ODOO_LOGFILE}"
)

if [[ "${ODOO_PROXY_MODE}" == "True" || "${ODOO_PROXY_MODE}" == "true" || "${ODOO_PROXY_MODE}" == "1" ]]; then
  args+=(--proxy-mode)
fi

exec odoo "${args[@]}"
