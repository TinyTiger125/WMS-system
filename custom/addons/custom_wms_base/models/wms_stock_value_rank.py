from odoo import api, fields, models


class CustomWmsStockValueRank(models.Model):
    _name = "custom.wms.stock.value.rank"
    _description = "WMS Stock Value Rank"
    _order = "snapshot_date desc, rank asc, id asc"

    snapshot_date = fields.Date(string="统计日期", required=True, index=True, default=fields.Date.context_today)
    rank = fields.Integer(string="排名", required=True)
    product_tmpl_id = fields.Many2one("product.template", string="商品", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", string="规格", required=True, ondelete="cascade")
    qty_available = fields.Float(string="库存数量")
    unit_cost = fields.Float(string="估算单价")
    valuation_basis = fields.Selection(
        [("standard", "成本价"), ("declared", "申报价"), ("list", "销售价"), ("fallback", "估值回退")],
        string="估值依据",
        required=True,
    )
    company_id = fields.Many2one("res.company", string="公司", required=True, default=lambda self: self.env.company, index=True)
    company_currency_id = fields.Many2one(
        "res.currency",
        string="公司币种",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    stock_value = fields.Monetary(string="库存金额", currency_field="company_currency_id")

    _sql_constraints = [
        ("uniq_company_date_product", "unique(company_id, snapshot_date, product_tmpl_id)", "同一天同一公司同一商品只能保留一条排名记录。"),
    ]

    @api.model
    def _estimate_unit_cost(self, product):
        if product.standard_price > 0:
            return product.standard_price, "standard"
        if product.product_tmpl_id.declared_value > 0:
            return product.product_tmpl_id.declared_value, "declared"
        if product.list_price > 0:
            return product.list_price, "list"
        return 0.0, "fallback"

    @api.model
    def refresh_top10(self, company=None, snapshot_date=None):
        company = company or self.env.company
        snapshot_date = snapshot_date or fields.Date.today()
        self.search([("company_id", "=", company.id), ("snapshot_date", "=", snapshot_date)]).unlink()

        grouped = self.env["stock.quant"].read_group(
            [
                ("company_id", "=", company.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0),
                ("product_id.type", "=", "consu"),
                ("product_id.is_storable", "=", True),
            ],
            fields=["product_id", "quantity:sum"],
            groupby=["product_id"],
            lazy=False,
        )

        rows = []
        for item in grouped:
            product_id = item.get("product_id") and item["product_id"][0]
            if not product_id:
                continue
            product = self.env["product.product"].browse(product_id)
            qty = item.get("quantity", 0.0) or 0.0
            unit_cost, basis = self._estimate_unit_cost(product)
            rows.append(
                {
                    "product": product,
                    "qty": qty,
                    "unit_cost": unit_cost,
                    "basis": basis,
                    "stock_value": qty * unit_cost,
                }
            )

        rows.sort(key=lambda r: r["stock_value"], reverse=True)
        for idx, row in enumerate(rows[:10], start=1):
            self.create(
                {
                    "snapshot_date": snapshot_date,
                    "rank": idx,
                    "product_tmpl_id": row["product"].product_tmpl_id.id,
                    "product_id": row["product"].id,
                    "qty_available": row["qty"],
                    "unit_cost": row["unit_cost"],
                    "valuation_basis": row["basis"],
                    "stock_value": row["stock_value"],
                    "company_id": company.id,
                }
            )
        return True
