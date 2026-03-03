from odoo import models
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @staticmethod
    def _has_cancel_permission(user):
        return user.has_group("base.group_system") or user.has_group("custom_wms_base.group_wms_boss")

    def button_confirm(self):
        for order in self:
            if not order.partner_id:
                raise ValidationError("采购单必须填写供应商。")
            if not order.order_line:
                raise ValidationError("采购单至少需要一条商品明细。")
            invalid_qty_lines = order.order_line.filtered(lambda line: line.product_qty <= 0)
            if invalid_qty_lines:
                raise ValidationError("采购明细数量必须大于 0。")
            invalid_price_lines = order.order_line.filtered(lambda line: line.price_unit < 0)
            if invalid_price_lines:
                raise ValidationError("采购明细单价不能为负数。")

        result = super().button_confirm()
        audit = self.env["custom.wms.audit.log"]
        for order in self:
            audit.create_event("purchase_confirm", order, f"采购单已确认：{order.name}")
        return result

    def button_cancel(self):
        if not self._has_cancel_permission(self.env.user):
            raise UserError("只有老板角色可以取消采购单。")
        result = super().button_cancel()
        audit = self.env["custom.wms.audit.log"]
        for order in self:
            audit.create_event("purchase_cancel", order, f"采购单已取消：{order.name}")
        return result

    def action_open_next_receipt(self):
        self.ensure_one()
        action = self.env["custom.wms.flow.step"].resolve_next_action(self, trigger_key="po_to_receipt")
        if action:
            return action
        pickings = self.picking_ids.filtered(lambda p: p.picking_type_code == "incoming" and p.state != "cancel")
        if not pickings:
            raise UserError("当前采购单还没有可处理的入库单。")
        action = self.env.ref("stock.action_picking_tree_incoming").sudo().read()[0]
        action["domain"] = [("id", "in", pickings.ids)]
        if len(pickings) == 1:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    def action_confirm_and_open_receipt(self):
        self.ensure_one()
        if self.state in ("draft", "sent", "to approve"):
            self.button_confirm()
        return self.action_open_next_receipt()
