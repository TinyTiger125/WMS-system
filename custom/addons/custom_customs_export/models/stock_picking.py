from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_open_customs_export_wizard(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("custom_customs_export.action_customs_export_wizard")
        action["context"] = {
            "active_model": "stock.picking",
            "active_ids": self.ids,
        }
        return action

