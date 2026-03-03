#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB_NAME="${DB_NAME:-odoo19_dev}"
ODOO_CONF="${ODOO_CONF:-$ROOT_DIR/odoo.conf}"

source .venv/bin/activate
python -m odoo shell -c "$ODOO_CONF" -d "$DB_NAME" --no-http <<'PY'
from lxml import etree

root_menu = env.ref('custom_wms_base.menu_custom_wms_root', raise_if_not_found=False)
if not root_menu:
    raise SystemExit('FAIL: missing custom_wms_base.menu_custom_wms_root')

users = {
    'boss_demo': {
        'must_see': {
            'custom_wms_base.menu_custom_wms_purchase',
            'custom_wms_base.menu_custom_wms_receipts',
            'custom_wms_base.menu_custom_wms_sales',
            'custom_wms_base.menu_custom_wms_deliveries',
        },
        'must_hide': set(),
    },
    'warehouse_demo': {
        'must_see': {
            'custom_wms_base.menu_custom_wms_receipts',
            'custom_wms_base.menu_custom_wms_deliveries',
        },
        'must_hide': {
            'custom_wms_base.menu_custom_wms_purchase',
            'custom_wms_base.menu_custom_wms_sales',
        },
    },
    'service_demo': {
        'must_see': {
            'custom_wms_base.menu_custom_wms_service_ticket_list_menu',
        },
        'must_hide': {
            'custom_wms_base.menu_custom_wms_purchase',
            'custom_wms_base.menu_custom_wms_receipts',
            'custom_wms_base.menu_custom_wms_sales',
            'custom_wms_base.menu_custom_wms_deliveries',
        },
    },
}

issues = []
print('Role Access Scan Start')

for login, rules in users.items():
    user = env['res.users'].sudo().search([('login', '=', login)], limit=1)
    if not user:
        issues.append(f'[{login}] missing user')
        continue

    visible_ids = set(env['ir.ui.menu'].with_user(user)._visible_menu_ids())

    def menu_visible(xmlid):
        menu = env.ref(xmlid, raise_if_not_found=False)
        return bool(menu and menu.id in visible_ids)

    for xmlid in sorted(rules['must_see']):
        if not menu_visible(xmlid):
            issues.append(f'[{login}] should see menu but hidden: {xmlid}')

    for xmlid in sorted(rules['must_hide']):
        if menu_visible(xmlid):
            issues.append(f'[{login}] should hide menu but visible: {xmlid}')

    # Validate all visible act_window menus under WMS root: model + list-field read
    visible_menus = env['ir.ui.menu'].sudo().browse(sorted(visible_ids))
    for menu in visible_menus:
        if menu.id != root_menu.id and str(root_menu.id) not in (menu.parent_path or ''):
            continue
        if not menu.action or menu.action._name != 'ir.actions.act_window':
            continue

        action = menu.action.sudo()
        model_name = action.res_model
        if not model_name or model_name not in env:
            continue

        model = env[model_name].with_user(user)
        if not model.check_access_rights('read', raise_exception=False):
            issues.append(f'[{login}] menu {menu.complete_name} has no read access on {model_name}')
            continue

        modes = [m.strip() for m in (action.view_mode or '').split(',') if m.strip()]
        if 'list' not in modes:
            continue

        try:
            views = action.get_views([(False, 'list')])
            list_view = views['views'].get('list')
            if not list_view:
                continue
            arch = etree.fromstring(list_view['arch'])
            fields = []
            for node in arch.xpath('//field[@name]'):
                fname = node.get('name')
                if fname in model._fields and fname not in fields:
                    fields.append(fname)
            rec = model.search([], limit=1)
            if rec and fields:
                rec.read(fields)
        except Exception as exc:
            issues.append(f'[{login}] menu {menu.complete_name} list-read failed: {str(exc).splitlines()[0][:220]}')

if issues:
    print('Role Access Scan FAILED')
    for item in issues:
        print(' -', item)
    raise SystemExit(1)

print('Role Access Scan PASSED')
PY
