from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    wms_role_boss = fields.Boolean(string="老板（采购+销售）", compute="_compute_wms_roles", inverse="_inverse_wms_role_boss")
    wms_role_warehouse = fields.Boolean(string="库管", compute="_compute_wms_roles", inverse="_inverse_wms_role_warehouse")
    wms_role_sales = fields.Boolean(string="销售", compute="_compute_wms_roles", inverse="_inverse_wms_role_sales")
    wms_role_service = fields.Boolean(string="客服", compute="_compute_wms_roles", inverse="_inverse_wms_role_service")
    wms_role_customer = fields.Boolean(string="客户", compute="_compute_wms_roles", inverse="_inverse_wms_role_customer")

    wms_can_purchase_order = fields.Boolean(string="可采购下单", compute="_compute_wms_capabilities")
    wms_can_purchase_receipt = fields.Boolean(string="可采购入库", compute="_compute_wms_capabilities")
    wms_can_sales_order = fields.Boolean(string="可销售下单", compute="_compute_wms_capabilities")
    wms_can_sales_delivery = fields.Boolean(string="可销售出库", compute="_compute_wms_capabilities")
    wms_can_reporting = fields.Boolean(string="可看经营报表", compute="_compute_wms_capabilities")

    wms_feature_workspace = fields.Boolean(string="工作台与待办", compute="_compute_wms_features", inverse="_inverse_wms_feature_workspace")
    wms_feature_master_data = fields.Boolean(string="商品与主数据", compute="_compute_wms_features", inverse="_inverse_wms_feature_master_data")
    wms_feature_purchase_order = fields.Boolean(string="采购下单", compute="_compute_wms_features", inverse="_inverse_wms_feature_purchase_order")
    wms_feature_purchase_receipt = fields.Boolean(string="采购入库", compute="_compute_wms_features", inverse="_inverse_wms_feature_purchase_receipt")
    wms_feature_sales_order = fields.Boolean(string="销售下单", compute="_compute_wms_features", inverse="_inverse_wms_feature_sales_order")
    wms_feature_sales_delivery = fields.Boolean(string="销售出库", compute="_compute_wms_features", inverse="_inverse_wms_feature_sales_delivery")
    wms_feature_inventory = fields.Boolean(string="库存监控", compute="_compute_wms_features", inverse="_inverse_wms_feature_inventory")
    wms_feature_exception_center = fields.Boolean(string="异常中心", compute="_compute_wms_features", inverse="_inverse_wms_feature_exception_center")
    wms_feature_reporting = fields.Boolean(string="经营报表", compute="_compute_wms_features", inverse="_inverse_wms_feature_reporting")
    wms_feature_service_ticket = fields.Boolean(string="客服工单", compute="_compute_wms_features", inverse="_inverse_wms_feature_service_ticket")
    wms_feature_customer_selfservice = fields.Boolean(
        string="客户自助", compute="_compute_wms_features", inverse="_inverse_wms_feature_customer_selfservice"
    )

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
            user.wms_role_customer = user._is_in_group("custom_wms_base.group_wms_customer")

    def _inverse_wms_role_boss(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_boss", user.wms_role_boss)
            if user.wms_role_boss:
                user._apply_role_feature_bundle("boss")

    def _inverse_wms_role_warehouse(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_warehouse_ops", user.wms_role_warehouse)
            if user.wms_role_warehouse:
                user._apply_role_feature_bundle("warehouse")

    def _inverse_wms_role_sales(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_sales_ops", user.wms_role_sales)
            if user.wms_role_sales:
                user._apply_role_feature_bundle("sales")

    def _inverse_wms_role_service(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_service_ops", user.wms_role_service)
            if user.wms_role_service:
                user._apply_role_feature_bundle("service")

    def _inverse_wms_role_customer(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_customer", user.wms_role_customer)
            if user.wms_role_customer:
                user._apply_role_feature_bundle("customer")
                has_work_role = any(
                    user._is_in_group(xmlid)
                    for xmlid in (
                        "custom_wms_base.group_wms_boss",
                        "custom_wms_base.group_wms_warehouse_ops",
                        "custom_wms_base.group_wms_sales_ops",
                        "custom_wms_base.group_wms_service_ops",
                    )
                )
                if not has_work_role:
                    user._set_group_membership("custom_wms_base.group_wms_feature_workspace", False)

    def _compute_wms_capabilities(self):
        for user in self:
            user.wms_can_purchase_order = user._is_in_group("custom_wms_base.group_wms_feature_purchase_order")
            user.wms_can_purchase_receipt = user._is_in_group("custom_wms_base.group_wms_feature_purchase_receipt")
            user.wms_can_sales_order = user._is_in_group("custom_wms_base.group_wms_feature_sales_order")
            user.wms_can_sales_delivery = user._is_in_group("custom_wms_base.group_wms_feature_sales_delivery")
            user.wms_can_reporting = user._is_in_group("custom_wms_base.group_wms_feature_reporting")

    def _compute_wms_features(self):
        for user in self:
            user.wms_feature_workspace = user._is_in_group("custom_wms_base.group_wms_feature_workspace")
            user.wms_feature_master_data = user._is_in_group("custom_wms_base.group_wms_feature_master_data")
            user.wms_feature_purchase_order = user._is_in_group("custom_wms_base.group_wms_feature_purchase_order")
            user.wms_feature_purchase_receipt = user._is_in_group("custom_wms_base.group_wms_feature_purchase_receipt")
            user.wms_feature_sales_order = user._is_in_group("custom_wms_base.group_wms_feature_sales_order")
            user.wms_feature_sales_delivery = user._is_in_group("custom_wms_base.group_wms_feature_sales_delivery")
            user.wms_feature_inventory = user._is_in_group("custom_wms_base.group_wms_feature_inventory")
            user.wms_feature_exception_center = user._is_in_group("custom_wms_base.group_wms_feature_exception_center")
            user.wms_feature_reporting = user._is_in_group("custom_wms_base.group_wms_feature_reporting")
            user.wms_feature_service_ticket = user._is_in_group("custom_wms_base.group_wms_feature_service_ticket")
            user.wms_feature_customer_selfservice = user._is_in_group(
                "custom_wms_base.group_wms_feature_customer_selfservice"
            )

    def _inverse_wms_feature_workspace(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_workspace", user.wms_feature_workspace)

    def _inverse_wms_feature_master_data(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_master_data", user.wms_feature_master_data)

    def _inverse_wms_feature_purchase_order(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_purchase_order", user.wms_feature_purchase_order)

    def _inverse_wms_feature_purchase_receipt(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_purchase_receipt", user.wms_feature_purchase_receipt)

    def _inverse_wms_feature_sales_order(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_sales_order", user.wms_feature_sales_order)

    def _inverse_wms_feature_sales_delivery(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_sales_delivery", user.wms_feature_sales_delivery)

    def _inverse_wms_feature_inventory(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_inventory", user.wms_feature_inventory)

    def _inverse_wms_feature_exception_center(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_exception_center", user.wms_feature_exception_center)

    def _inverse_wms_feature_reporting(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_reporting", user.wms_feature_reporting)

    def _inverse_wms_feature_service_ticket(self):
        for user in self:
            user._set_group_membership("custom_wms_base.group_wms_feature_service_ticket", user.wms_feature_service_ticket)

    def _inverse_wms_feature_customer_selfservice(self):
        for user in self:
            user._set_group_membership(
                "custom_wms_base.group_wms_feature_customer_selfservice",
                user.wms_feature_customer_selfservice,
            )

    def _apply_role_feature_bundle(self, role_key):
        bundles = {
            "boss": [
                "custom_wms_base.group_wms_feature_workspace",
                "custom_wms_base.group_wms_feature_master_data",
                "custom_wms_base.group_wms_feature_purchase_order",
                "custom_wms_base.group_wms_feature_purchase_receipt",
                "custom_wms_base.group_wms_feature_sales_order",
                "custom_wms_base.group_wms_feature_sales_delivery",
                "custom_wms_base.group_wms_feature_inventory",
                "custom_wms_base.group_wms_feature_exception_center",
                "custom_wms_base.group_wms_feature_reporting",
                "custom_wms_base.group_wms_feature_service_ticket",
            ],
            "warehouse": [
                "custom_wms_base.group_wms_feature_workspace",
                "custom_wms_base.group_wms_feature_purchase_receipt",
                "custom_wms_base.group_wms_feature_sales_delivery",
                "custom_wms_base.group_wms_feature_inventory",
                "custom_wms_base.group_wms_feature_exception_center",
            ],
            "sales": [
                "custom_wms_base.group_wms_feature_workspace",
                "custom_wms_base.group_wms_feature_master_data",
                "custom_wms_base.group_wms_feature_sales_order",
            ],
            "service": [
                "custom_wms_base.group_wms_feature_workspace",
                "custom_wms_base.group_wms_feature_service_ticket",
            ],
            "customer": [
                "custom_wms_base.group_wms_feature_customer_selfservice",
            ],
        }
        for xmlid in bundles.get(role_key, []):
            self._set_group_membership(xmlid, True)
