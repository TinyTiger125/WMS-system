from odoo import api, fields, models


class CustomCnStockSnapshot(models.Model):
    _name = "custom.cn.stock.snapshot"
    _description = "CN Stock Snapshot"
    _order = "synced_at desc, id desc"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    product_id = fields.Many2one(
        "product.product",
        string="Variant",
        compute="_compute_product_id",
        store=True,
    )
    sku = fields.Char(string="SKU")
    available_qty = fields.Float(required=True, default=0.0)
    warehouse_code = fields.Char(required=True, default="CN")
    synced_at = fields.Datetime(default=fields.Datetime.now, required=True)
    note = fields.Text()

    _unique_product_warehouse = models.Constraint(
        "unique(product_tmpl_id, warehouse_code)",
        "Each product can only have one snapshot per warehouse code.",
    )

    @api.depends("product_tmpl_id")
    def _compute_product_id(self):
        for record in self:
            record.product_id = record.product_tmpl_id.product_variant_id

    def action_apply_to_product(self):
        for snapshot in self:
            snapshot.product_tmpl_id.cn_external_qty = snapshot.available_qty
