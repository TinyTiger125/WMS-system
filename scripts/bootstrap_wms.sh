#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Create it first with: python3.12 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

python -m odoo -c odoo.conf -d odoo19_dev \
  -i sale_management,purchase,stock,custom_wms_base,custom_cn_sync,custom_customs_export \
  -u custom_wms_base,custom_cn_sync,custom_customs_export \
  --without-demo \
  --no-http \
  --stop-after-init

# Ensure required trading currencies are available for product declaration/sales flows.
python -m odoo shell -c odoo.conf -d odoo19_dev --no-http <<'PY'
currencies = env["res.currency"].with_context(active_test=False).search([("name", "in", ["JPY", "CNY"])])
if currencies:
    currencies.write({"active": True})
print("Activated currencies:", ", ".join(currencies.mapped("name")))
PY

echo "WMS bootstrap completed for database: odoo19_dev"
