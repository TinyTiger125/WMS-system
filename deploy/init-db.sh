#!/usr/bin/env bash
set -euo pipefail

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=odoo}"
: "${DB_PASSWORD:=odoo}"
: "${ODOO_DB_NAME:=odoo19_prod}"
: "${ODOO_ADMIN_PASSWD:=admin}"
: "${ODOO_ADDONS_PATH:=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons}"
: "${ODOO_INIT_MODULES:=base,sale_management,purchase,stock,custom_wms_base,custom_customs_export}"
: "${ODOO_UPGRADE_MODULES:=custom_wms_base,custom_customs_export}"

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
  echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
  sleep 2
done

echo "[1/2] Initializing database ${ODOO_DB_NAME} with modules: ${ODOO_INIT_MODULES}"
odoo \
  --db_host="${DB_HOST}" \
  --db_port="${DB_PORT}" \
  --db_user="${DB_USER}" \
  --db_password="${DB_PASSWORD}" \
  -d "${ODOO_DB_NAME}" \
  --addons-path="${ODOO_ADDONS_PATH}" \
  -i "${ODOO_INIT_MODULES}" \
  --without-demo=all \
  --stop-after-init

echo "[2/2] Upgrading custom modules: ${ODOO_UPGRADE_MODULES}"
odoo \
  --db_host="${DB_HOST}" \
  --db_port="${DB_PORT}" \
  --db_user="${DB_USER}" \
  --db_password="${DB_PASSWORD}" \
  -d "${ODOO_DB_NAME}" \
  --addons-path="${ODOO_ADDONS_PATH}" \
  -u "${ODOO_UPGRADE_MODULES}" \
  --without-demo=all \
  --stop-after-init

echo "Database init finished."
