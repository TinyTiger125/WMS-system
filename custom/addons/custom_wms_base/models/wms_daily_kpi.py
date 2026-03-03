from datetime import datetime, time, timedelta

from odoo import api, fields, models


class CustomWmsDailyKpi(models.Model):
    _name = "custom.wms.daily.kpi"
    _description = "WMS Daily KPI"
    _order = "report_date desc, id desc"

    report_date = fields.Date(string="统计日期", required=True, index=True)
    purchase_order_count = fields.Integer(string="采购确认单数")
    sale_order_count = fields.Integer(string="销售确认单数")
    inbound_qty = fields.Float(string="入库数量")
    outbound_qty = fields.Float(string="出库数量")
    sale_revenue = fields.Monetary(string="销售收入", currency_field="company_currency_id")
    estimated_gross_profit = fields.Monetary(string="预计毛利", currency_field="company_currency_id")
    estimated_margin_rate = fields.Float(string="毛利率(%)", digits=(16, 2))
    end_stock_qty = fields.Float(string="期末库存数量")
    company_currency_id = fields.Many2one(
        "res.currency",
        string="公司币种",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    end_stock_value = fields.Monetary(string="期末库存金额", currency_field="company_currency_id")
    missing_cost_product_count = fields.Integer(string="无成本价商品数")
    low_stock_count = fields.Integer(string="低库存商品数")
    high_stock_count = fields.Integer(string="高库存商品数")
    company_id = fields.Many2one("res.company", string="公司", default=lambda self: self.env.company, required=True, index=True)
    note = fields.Char(string="备注")

    _sql_constraints = [
        ("uniq_company_date", "unique(company_id, report_date)", "同一公司同一天只能有一条日报。"),
    ]

    @api.model
    def _day_range(self, report_date):
        start_dt = datetime.combine(report_date, time.min)
        end_dt = start_dt + timedelta(days=1)
        return fields.Datetime.to_string(start_dt), fields.Datetime.to_string(end_dt)

    @api.model
    def upsert_for_date(self, report_date, company=None):
        company = company or self.env.company
        start_dt, end_dt = self._day_range(report_date)

        purchase_count = self.env["purchase.order"].search_count(
            [
                ("company_id", "=", company.id),
                ("state", "in", ("purchase", "done")),
                ("date_approve", ">=", start_dt),
                ("date_approve", "<", end_dt),
            ]
        )
        sale_count = self.env["sale.order"].search_count(
            [
                ("company_id", "=", company.id),
                ("state", "in", ("sale", "done")),
                ("date_order", ">=", start_dt),
                ("date_order", "<", end_dt),
            ]
        )
        sale_orders = self.env["sale.order"].search(
            [
                ("company_id", "=", company.id),
                ("state", "in", ("sale", "done")),
                ("date_order", ">=", start_dt),
                ("date_order", "<", end_dt),
            ]
        )

        inbound_moves = self.env["stock.move"].search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("picking_id.picking_type_code", "=", "incoming"),
                ("date", ">=", start_dt),
                ("date", "<", end_dt),
            ]
        )
        outbound_moves = self.env["stock.move"].search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("picking_id.picking_type_code", "=", "outgoing"),
                ("date", ">=", start_dt),
                ("date", "<", end_dt),
            ]
        )

        quants = self.env["stock.quant"].search(
            [
                ("company_id", "=", company.id),
                ("location_id.usage", "=", "internal"),
            ]
        )
        stock_quants = quants.filtered(
            lambda q: q.quantity > 0 and q.product_id.type == "consu" and q.product_id.is_storable
        )
        end_stock_qty = sum(stock_quants.mapped("quantity"))
        end_stock_value = 0.0
        missing_cost_products = self.env["product.product"]
        for quant in stock_quants:
            product = quant.product_id
            # Priority: standard cost -> declared value -> sale price (estimated)
            unit_cost = product.standard_price or product.product_tmpl_id.declared_value or product.list_price or 0.0
            end_stock_value += quant.quantity * unit_cost
            if product.standard_price <= 0:
                missing_cost_products |= product

        low_stock_count = self.env["custom.wms.stock.exception"].search_count(
            [("company_id", "=", company.id), ("status", "=", "low")]
        )
        high_stock_count = self.env["custom.wms.stock.exception"].search_count(
            [("company_id", "=", company.id), ("status", "=", "high")]
        )

        vals = {
            "report_date": report_date,
            "company_id": company.id,
            "purchase_order_count": purchase_count,
            "sale_order_count": sale_count,
            "inbound_qty": sum(inbound_moves.mapped("quantity")),
            "outbound_qty": sum(outbound_moves.mapped("quantity")),
            "sale_revenue": sum(sale_orders.mapped("amount_untaxed")),
            "estimated_gross_profit": sum(sale_orders.mapped("wms_margin_amount")),
            "end_stock_qty": end_stock_qty,
            "end_stock_value": end_stock_value,
            "missing_cost_product_count": len(missing_cost_products),
            "low_stock_count": low_stock_count,
            "high_stock_count": high_stock_count,
        }
        vals["estimated_margin_rate"] = (
            vals["estimated_gross_profit"] / vals["sale_revenue"] * 100.0 if vals["sale_revenue"] else 0.0
        )
        record = self.search([("company_id", "=", company.id), ("report_date", "=", report_date)], limit=1)
        if record:
            record.write(vals)
            return record
        return self.create(vals)

    @api.model
    def _cron_generate_daily_kpi(self):
        self.env["custom.wms.stock.exception"].refresh_exceptions()
        self.env["custom.wms.stock.value.rank"].refresh_top10()
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)
        self.upsert_for_date(yesterday)
        self.upsert_for_date(today)

    @api.model
    def action_generate_today(self):
        self._cron_generate_daily_kpi()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "list,pivot,graph",
            "target": "current",
        }
