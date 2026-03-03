from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @staticmethod
    def _has_cancel_permission(user):
        return user.has_group("base.group_system") or user.has_group("custom_wms_base.group_wms_boss")

    def _check_no_negative_stock(self):
        for picking in self.filtered(lambda p: p.picking_type_code == "outgoing" and p.state not in ("done", "cancel")):
            demand_by_product = defaultdict(float)
            for move in picking.move_ids.filtered(lambda m: m.product_id.type != "service" and m.quantity > 0):
                demand_by_product[move.product_id] += move.quantity

            insufficient = []
            for product, demand in demand_by_product.items():
                available_qty = product.with_context(location=picking.location_id.id).qty_available
                if available_qty < demand:
                    insufficient.append((product.display_name, available_qty, demand))

            if insufficient:
                lines = [f"{name}（可用 {avail:.3f}，需求 {need:.3f}）" for name, avail, need in insufficient[:10]]
                raise ValidationError("库存不足，无法出库：\n" + "\n".join(lines))

    def button_validate(self):
        if not self.env.user.has_group("custom_wms_base.group_wms_boss"):
            self._check_no_negative_stock()

        result = super().button_validate()

        self.env["custom.wms.stock.exception"].refresh_exceptions()
        audit = self.env["custom.wms.audit.log"]
        for picking in self.filtered(lambda p: p.state == "done"):
            audit.create_event("picking_validate", picking, f"库存单据已过账：{picking.name}")
        return result

    def action_cancel(self):
        if not self._has_cancel_permission(self.env.user):
            raise UserError("只有老板角色可以取消出入库单。")
        result = super().action_cancel()
        self.env["custom.wms.stock.exception"].refresh_exceptions()
        audit = self.env["custom.wms.audit.log"]
        for picking in self:
            audit.create_event("picking_cancel", picking, f"库存单据已取消：{picking.name}")
        return result

    def action_open_next_sales_step(self):
        self.ensure_one()
        action = self.env["custom.wms.flow.step"].resolve_next_action(self, trigger_key="inbound_done_to_sales")
        if not action:
            action = self.env.ref("custom_wms_base.action_custom_wms_sales_flow").sudo().read()[0]
        return action
