from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    wms_role_boss = fields.Boolean(string="老板（采购+销售）", compute="_compute_wms_roles", inverse="_inverse_wms_role_boss")
    wms_role_warehouse = fields.Boolean(string="库管", compute="_compute_wms_roles", inverse="_inverse_wms_role_warehouse")
    wms_role_sales = fields.Boolean(string="销售", compute="_compute_wms_roles", inverse="_inverse_wms_role_sales")
    wms_role_service = fields.Boolean(string="客服", compute="_compute_wms_roles", inverse="_inverse_wms_role_service")

    wms_can_purchase_order = fields.Boolean(string="可采购下单", compute="_compute_wms_capabilities")
    wms_can_purchase_receipt = fields.Boolean(string="可采购入库", compute="_compute_wms_capabilities")
    wms_can_sales_order = fields.Boolean(string="可销售下单", compute="_compute_wms_capabilities")
    wms_can_sales_delivery = fields.Boolean(string="可销售出库", compute="_compute_wms_capabilities")
    wms_can_reporting = fields.Boolean(string="可看经营报表", compute="_compute_wms_capabilities")

    def _is_in_group(self, xmlid):
        self.ensure_one()
        return self.has_group(xmlid)

    def _set_group_membership(self, xmlid, enabled):
        group = self.env.ref(xmlid)
        base_user = self.env.ref("base.group_user")
        for user in self:
            group_ids = user.group_ids
            if enabled and group not in group_ids:
                user.group_ids = [(4, group.id), (4, base_user.id)]
            if not enabled and group in group_ids:
                user.group_ids = [(3, group.id)]

    def _compute_wms_roles(self):
        for user in self:
            user.wms_role_boss = user._is_in_group("custom_wms_base.group_wms_boss")
            user.wms_role_warehouse = user._is_in_group("custom_wms_base.group_wms_warehouse_ops")
            user.wms_role_sales = user._is_in_group("custom_wms_base.group_wms_sales_ops")
            user.wms_role_service = user._is_in_group("custom_wms_base.group_wms_service_ops")

    def _inverse_wms_role_boss(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_boss", user.wms_role_boss)

    def _inverse_wms_role_warehouse(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_warehouse_ops", user.wms_role_warehouse)

    def _inverse_wms_role_sales(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_sales_ops", user.wms_role_sales)

    def _inverse_wms_role_service(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_service_ops", user.wms_role_service)

    def _compute_wms_capabilities(self):
        for user in self:
            is_boss = user._is_in_group("custom_wms_base.group_wms_boss")
            is_wh = user._is_in_group("custom_wms_base.group_wms_warehouse_ops")
            is_sales = user._is_in_group("custom_wms_base.group_wms_sales_ops")

            user.wms_can_purchase_order = is_boss
            user.wms_can_purchase_receipt = is_boss or is_wh
            user.wms_can_sales_order = is_boss or is_sales
            user.wms_can_sales_delivery = is_boss or is_wh
            user.wms_can_reporting = is_boss or is_wh
