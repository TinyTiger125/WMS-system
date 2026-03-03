from odoo import api, fields, models


class CustomWmsRoleDashboard(models.Model):
    _name = "custom.wms.role.dashboard"
    _description = "WMS Role Dashboard"
    _order = "as_of desc, id desc"

    name = fields.Char(string="名称", compute="_compute_name", store=True)
    role = fields.Selection(
        [("boss", "老板"), ("warehouse", "库管"), ("service", "客服")],
        string="角色",
        required=True,
        index=True,
    )
    user_id = fields.Many2one("res.users", string="用户", required=True, default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one("res.company", string="公司", required=True, default=lambda self: self.env.company, index=True)
    as_of = fields.Datetime(string="统计时间", default=fields.Datetime.now, required=True)
    company_currency_id = fields.Many2one(
        "res.currency",
        string="公司币种",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Boss metrics
    boss_stock_value = fields.Monetary(string="库存压资金额", currency_field="company_currency_id")
    boss_low_stock_count = fields.Integer(string="低库存商品数")
    boss_missing_cost_count = fields.Integer(string="无成本价商品数")
    boss_pending_purchase_count = fields.Integer(string="待采购确认")
    boss_pending_delivery_count = fields.Integer(string="待销售出库")

    # Warehouse metrics
    wh_incoming_in_transit = fields.Integer(string="在途入库单")
    wh_outgoing_in_transit = fields.Integer(string="在途出库单")
    wh_partial_contract_count = fields.Integer(string="分批合同数")
    wh_stock_qty_total = fields.Float(string="当前库存总量")
    wh_exception_count = fields.Integer(string="库存异常数")

    # Service metrics
    service_open_count = fields.Integer(string="待处理工单")
    service_pending_count = fields.Integer(string="待客户回复")
    service_overdue_count = fields.Integer(string="逾期工单")
    service_today_new_count = fields.Integer(string="今日新建工单")

    _sql_constraints = [
        ("uniq_role_user_company", "unique(role, user_id, company_id)", "同一用户同一公司同一角色只能有一条仪表盘记录。"),
    ]

    @api.depends("role", "user_id")
    def _compute_name(self):
        role_map = {"boss": "老板", "warehouse": "库管", "service": "客服"}
        for rec in self:
            rec.name = f"{role_map.get(rec.role, '角色')}仪表盘 - {rec.user_id.name}"

    @api.model
    def _get_or_create_dashboard(self, role):
        dashboard = self.search(
            [("role", "=", role), ("user_id", "=", self.env.user.id), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        if not dashboard:
            dashboard = self.create({"role": role, "user_id": self.env.user.id, "company_id": self.env.company.id})
        dashboard.refresh_metrics()
        return dashboard

    def refresh_metrics(self):
        for rec in self:
            rec.as_of = fields.Datetime.now()
            cid = rec.company_id.id
            if rec.role == "boss":
                rec._refresh_boss_metrics(cid)
            elif rec.role == "warehouse":
                rec._refresh_warehouse_metrics(cid)
            elif rec.role == "service":
                rec._refresh_service_metrics(cid)

    def _refresh_boss_metrics(self, company_id):
        self.ensure_one()
        today_kpi = self.env["custom.wms.daily.kpi"].search(
            [("company_id", "=", company_id), ("report_date", "=", fields.Date.today())], limit=1
        )
        self.boss_stock_value = today_kpi.end_stock_value if today_kpi else 0.0
        self.boss_low_stock_count = self.env["custom.wms.stock.exception"].search_count(
            [("company_id", "=", company_id), ("status", "=", "low")]
        )
        self.boss_missing_cost_count = self.env["custom.wms.stock.exception"].search_count(
            [("company_id", "=", company_id), ("status", "=", "cost_missing")]
        )
        self.boss_pending_purchase_count = self.env["purchase.order"].search_count(
            [("company_id", "=", company_id), ("state", "in", ("draft", "sent", "to approve"))]
        )
        self.boss_pending_delivery_count = self.env["stock.picking"].search_count(
            [("company_id", "=", company_id), ("picking_type_code", "=", "outgoing"), ("state", "not in", ("done", "cancel"))]
        )

    def _refresh_warehouse_metrics(self, company_id):
        self.ensure_one()
        self.wh_incoming_in_transit = self.env["stock.picking"].search_count(
            [("company_id", "=", company_id), ("picking_type_code", "=", "incoming"), ("state", "not in", ("done", "cancel"))]
        )
        self.wh_outgoing_in_transit = self.env["stock.picking"].search_count(
            [("company_id", "=", company_id), ("picking_type_code", "=", "outgoing"), ("state", "not in", ("done", "cancel"))]
        )
        orders = self.env["purchase.order"].search([("company_id", "=", company_id), ("state", "in", ("purchase", "done"))])
        self.wh_partial_contract_count = len(
            orders.filtered(
                lambda o: any(p.state == "done" for p in o.picking_ids)
                and any(p.state not in ("done", "cancel") for p in o.picking_ids)
            )
        )
        quants = self.env["stock.quant"].search([("company_id", "=", company_id), ("location_id.usage", "=", "internal")])
        self.wh_stock_qty_total = sum(quants.filtered(lambda q: q.quantity > 0).mapped("quantity"))
        self.wh_exception_count = self.env["custom.wms.stock.exception"].search_count([("company_id", "=", company_id)])

    def _refresh_service_metrics(self, company_id):
        self.ensure_one()
        ticket = self.env["custom.wms.service.ticket"]
        today = fields.Date.today()
        self.service_open_count = ticket.search_count(
            [("company_id", "=", company_id), ("state", "in", ("new", "in_progress")), ("responsible_id", "=", self.user_id.id)]
        )
        self.service_pending_count = ticket.search_count(
            [("company_id", "=", company_id), ("state", "=", "pending"), ("responsible_id", "=", self.user_id.id)]
        )
        self.service_overdue_count = ticket.search_count(
            [
                ("company_id", "=", company_id),
                ("state", "in", ("new", "in_progress", "pending")),
                ("deadline", "!=", False),
                ("deadline", "<", today),
                ("responsible_id", "=", self.user_id.id),
            ]
        )
        self.service_today_new_count = ticket.search_count(
            [
                ("company_id", "=", company_id),
                ("create_date", ">=", fields.Datetime.to_string(fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))),
            ]
        )

    @api.model
    def _open_dashboard(self, role):
        rec = self._get_or_create_dashboard(role)
        return {
            "type": "ir.actions.act_window",
            "name": rec.name,
            "res_model": self._name,
            "view_mode": "form",
            "res_id": rec.id,
            "target": "current",
        }

    @api.model
    def action_open_boss_dashboard(self):
        return self._open_dashboard("boss")

    @api.model
    def action_open_warehouse_dashboard(self):
        return self._open_dashboard("warehouse")

    @api.model
    def action_open_service_dashboard(self):
        return self._open_dashboard("service")

    def action_open_pending_purchase(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "待采购确认",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id), ("state", "in", ("draft", "sent", "to approve"))],
        }

    def action_open_pending_delivery(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "待销售出库",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("picking_type_code", "=", "outgoing"),
                ("state", "not in", ("done", "cancel")),
            ],
        }

    def action_open_low_stock(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "低库存预警",
            "res_model": "custom.wms.stock.exception",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id), ("status", "=", "low")],
        }

    def action_open_missing_cost(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "无成本价预警",
            "res_model": "custom.wms.stock.exception",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id), ("status", "=", "cost_missing")],
        }

    def action_open_incoming_transit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "在途入库单",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("picking_type_code", "=", "incoming"),
                ("state", "not in", ("done", "cancel")),
            ],
        }

    def action_open_outgoing_transit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "在途出库单",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("picking_type_code", "=", "outgoing"),
                ("state", "not in", ("done", "cancel")),
            ],
        }

    def action_open_service_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "我的待处理工单",
            "res_model": "custom.wms.service.ticket",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("responsible_id", "=", self.user_id.id),
                ("state", "in", ("new", "in_progress", "pending")),
            ],
        }
