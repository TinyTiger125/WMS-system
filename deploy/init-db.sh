#!/usr/bin/env bash
set -euo pipefail

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=odoo}"
: "${DB_PASSWORD:=odoo}"
: "${ODOO_DB_NAME:=odoo19_prod}"
: "${ODOO_ADMIN_PASSWD:=admin}"
: "${ODOO_ADDONS_PATH:=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons}"
: "${ODOO_INIT_MODULES:=base,sale_management,purchase,stock,custom_wms_base,custom_customs_export,custom_cn_sync}"
: "${ODOO_UPGRADE_MODULES:=custom_wms_base,custom_customs_export,custom_cn_sync}"
: "${ODOO_FORCE_LANG:=zh_CN}"

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

if [[ -n "${ODOO_FORCE_LANG}" ]]; then
  echo "[lang] Enforcing default language: ${ODOO_FORCE_LANG}"
  odoo shell \
    --db_host="${DB_HOST}" \
    --db_port="${DB_PORT}" \
    --db_user="${DB_USER}" \
    --db_password="${DB_PASSWORD}" \
    -d "${ODOO_DB_NAME}" \
    --addons-path="${ODOO_ADDONS_PATH}" <<'PY'
import os
lang_code = os.environ.get('ODOO_FORCE_LANG') or 'zh_CN'

# Ensure language exists and is active.
lang = env['res.lang'].sudo().search([('code', '=', lang_code)], limit=1)
if not lang:
    env['base.language.install'].sudo().create({'lang': lang_code}).lang_install()
    lang = env['res.lang'].sudo().search([('code', '=', lang_code)], limit=1)
if lang and not lang.active:
    lang.sudo().write({'active': True})

# Enforce language for internal users and company partner.
users = env['res.users'].sudo().search([('share', '=', False)])
users.write({'lang': lang_code})
users.mapped('partner_id').sudo().write({'lang': lang_code})
company_partner = env.company.partner_id.sudo()
if company_partner:
    company_partner.write({'lang': lang_code})
print(f"Language forced to {lang_code}. Internal users updated: {len(users)}")
PY
fi

echo "Database init finished."
