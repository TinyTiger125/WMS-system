from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        result = super()._action_done()
        outgoing_pickings = self.filtered(lambda p: p.picking_type_code == "outgoing" and p.state == "done")
        sync_job_model = self.env["custom.cn.sync.job"]
        for picking in outgoing_pickings:
            existing = sync_job_model.search(
                [
                    ("picking_id", "=", picking.id),
                    ("direction", "=", "outbound"),
                    ("state", "in", ("pending", "processing", "done")),
                ],
                limit=1,
            )
            if not existing:
                sync_job_model.create_from_picking(picking)
        return result
