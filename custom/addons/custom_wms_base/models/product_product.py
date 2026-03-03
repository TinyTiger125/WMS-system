from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def write(self, vals):
        track_cost = "standard_price" in vals
        old_cost = {}
        if track_cost:
            for product in self:
                old_cost[product.id] = product.standard_price

        result = super().write(vals)

        if track_cost:
            history_model = self.env["custom.wms.price.history"]
            for product in self:
                history_model.log_change(
                    product_tmpl=product.product_tmpl_id,
                    change_type="cost",
                    old_value=old_cost.get(product.id, 0.0),
                    new_value=product.standard_price,
                    currency=product.currency_id,
                    source_model=self._name,
                    source_ref=product.display_name,
                    note="成本价更新",
                )
        return result
