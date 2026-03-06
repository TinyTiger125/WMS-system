from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WmsUserQuickCreate(models.TransientModel):
    _name = "custom.wms.user.quick.create"
    _description = "WMS Quick User Create"

    name = fields.Char(string="姓名", required=True)
    login = fields.Char(string="登录账号", required=True)
    password = fields.Char(string="登录密码", required=True)
    active = fields.Boolean(string="启用账号", default=True)

    role_boss = fields.Boolean(string="老板（采购+销售）")
    role_warehouse = fields.Boolean(string="库管")
    role_sales = fields.Boolean(string="销售")
    role_service = fields.Boolean(string="客服")

    @api.constrains("role_boss", "role_warehouse", "role_sales", "role_service")
    def _check_has_any_role(self):
        for wizard in self:
            if not any([wizard.role_boss, wizard.role_warehouse, wizard.role_sales, wizard.role_service]):
                raise ValidationError("请至少勾选一个角色。")

    def _collect_group_ids(self):
        self.ensure_one()
        xmlids = ["base.group_user"]
        if self.role_boss:
            xmlids.append("custom_wms_base.group_wms_boss")
        if self.role_warehouse:
            xmlids.append("custom_wms_base.group_wms_warehouse_ops")
        if self.role_sales:
            xmlids.append("custom_wms_base.group_wms_sales_ops")
        if self.role_service:
            xmlids.append("custom_wms_base.group_wms_service_ops")
        return [self.env.ref(xmlid).id for xmlid in xmlids]

    def action_create_user(self):
        self.ensure_one()

        user_model = self.env["res.users"].sudo().with_context(no_reset_password=True)
        existing = user_model.search([("login", "=", self.login)], limit=1)
        if existing:
            raise UserError(_("账号 %s 已存在，请换一个登录账号。") % self.login)

        user = user_model.create(
            {
                "name": self.name,
                "login": self.login,
                "password": self.password,
                "active": self.active,
                "groups_id": [(6, 0, self._collect_group_ids())],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "账号详情",
            "res_model": "res.users",
            "res_id": user.id,
            "view_mode": "form",
            "target": "current",
        }
