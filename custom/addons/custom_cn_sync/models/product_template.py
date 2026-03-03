from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    cn_external_qty = fields.Float(string="CN External Qty", default=0.0)
    total_sellable_qty = fields.Float(
        string="Total Sellable Qty",
        compute="_compute_total_sellable_qty",
        digits="Product Unit of Measure",
    )

    def _compute_total_sellable_qty(self):
        for product in self:
            product.total_sellable_qty = product.qty_available + product.cn_external_qty

