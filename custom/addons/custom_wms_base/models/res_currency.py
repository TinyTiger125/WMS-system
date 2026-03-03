from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def action_activate_wms_currencies(self):
        currencies = self.with_context(active_test=False).search([("name", "in", ["JPY", "CNY"])])
        if currencies:
            currencies.write({"active": True})
        return True
