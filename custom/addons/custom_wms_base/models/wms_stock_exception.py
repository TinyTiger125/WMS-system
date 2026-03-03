from odoo import api, fields, models


class CustomWmsStockException(models.Model):
    _name = "custom.wms.stock.exception"
    _description = "WMS Stock Exception"
    _order = "status desc, shortage_rate desc, id desc"

    product_tmpl_id = fields.Many2one("product.template", string="商品", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", string="规格", required=True, ondelete="cascade")
    status = fields.Selection(
        [("low", "低库存"), ("high", "高库存"), ("cost_missing", "无成本价")],
        string="预警类型",
        required=True,
        index=True,
    )
    qty_available = fields.Float(string="当前可用")
    standard_price = fields.Float(string="成本价", related="product_id.standard_price", readonly=True)
    min_qty = fields.Float(string="最低库存阈值")
    max_qty = fields.Float(string="最高库存阈值")
    shortage_rate = fields.Float(string="偏离比例(%)")
    snapshot_time = fields.Datetime(string="快照时间", default=fields.Datetime.now, required=True)
    company_id = fields.Many2one("res.company", string="公司", default=lambda self: self.env.company, required=True)

    _sql_constraints = [
        ("uniq_company_product_status", "unique(company_id, product_tmpl_id, status)", "同一公司下同一商品同一预警类型只能保留一条记录。"),
    ]

    @api.model
    def refresh_exceptions(self):
        model = self.sudo()
        products = model.env["product.template"].with_context(active_test=False).search(
            [
                ("active", "=", True),
                ("type", "=", "consu"),
                ("is_storable", "=", True),
            ]
        )
        existing_rows = model.search([])
        existing_by_key = {(row.company_id.id, row.product_tmpl_id.id, row.status): row for row in existing_rows}
        keep_ids = set()
        now = fields.Datetime.now()

        for tmpl in products:
            product = tmpl.product_variant_id
            if not product:
                continue
            qty_available = product.qty_available
            min_qty = tmpl.wms_min_qty or 0.0
            max_qty = tmpl.wms_max_qty or 0.0
            company_id = tmpl.company_id.id or self.env.company.id
            statuses = []
            if min_qty > 0 and qty_available < min_qty:
                shortage_rate = ((min_qty - qty_available) / min_qty) * 100.0 if min_qty else 0.0
                statuses.append(("low", shortage_rate))
            if max_qty > 0 and qty_available > max_qty:
                shortage_rate = ((qty_available - max_qty) / max_qty) * 100.0 if max_qty else 0.0
                statuses.append(("high", shortage_rate))
            if qty_available > 0 and product.standard_price <= 0:
                statuses.append(("cost_missing", 0.0))

            for status, shortage_rate in statuses:
                existing = existing_by_key.get((company_id, tmpl.id, status))
                vals = {
                    "product_tmpl_id": tmpl.id,
                    "product_id": product.id,
                    "status": status,
                    "qty_available": qty_available,
                    "min_qty": min_qty,
                    "max_qty": max_qty,
                    "shortage_rate": shortage_rate,
                    "snapshot_time": now,
                    "company_id": company_id,
                }
                if existing:
                    existing.write(vals)
                    keep_ids.add(existing.id)
                else:
                    keep_ids.add(model.create(vals).id)

        stale_records = existing_rows.filtered(lambda r: r.id not in keep_ids)
        if stale_records:
            stale_records.unlink()
        return True

    @api.model
    def _cron_refresh_exceptions(self):
        self.refresh_exceptions()

    @api.model
    def action_refresh_exceptions(self):
        self.refresh_exceptions()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "list,form",
            "target": "current",
        }
