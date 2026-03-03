from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    wms_margin_amount = fields.Monetary(
        string="预计毛利",
        currency_field="currency_id",
        compute="_compute_wms_margin",
    )
    wms_margin_rate = fields.Float(
        string="毛利率(%)",
        compute="_compute_wms_margin",
        digits=(16, 2),
    )

    @staticmethod
    def _has_cancel_permission(user):
        return user.has_group("base.group_system") or user.has_group("custom_wms_base.group_wms_boss")

    @api.depends("order_line.wms_margin_amount", "amount_untaxed")
    def _compute_wms_margin(self):
        for order in self:
            margin_amount = sum(order.order_line.mapped("wms_margin_amount"))
            order.wms_margin_amount = margin_amount
            order.wms_margin_rate = (margin_amount / order.amount_untaxed * 100.0) if order.amount_untaxed else 0.0

    def action_confirm(self):
        for order in self:
            if not order.partner_id:
                raise ValidationError("销售单必须填写客户。")
            if not order.order_line:
                raise ValidationError("销售单至少需要一条商品明细。")
            invalid_qty_lines = order.order_line.filtered(lambda line: line.product_uom_qty <= 0)
            if invalid_qty_lines:
                raise ValidationError("销售明细数量必须大于 0。")
            invalid_price_lines = order.order_line.filtered(lambda line: line.price_unit < 0)
            if invalid_price_lines:
                raise ValidationError("销售明细单价不能为负数。")

        result = super().action_confirm()
        audit = self.env["custom.wms.audit.log"]
        for order in self:
            audit.create_event("sale_confirm", order, f"销售单已确认：{order.name}")
        return result

    def action_cancel(self):
        if not self._has_cancel_permission(self.env.user):
            raise UserError("只有老板角色可以取消销售单。")
        result = super().action_cancel()
        audit = self.env["custom.wms.audit.log"]
        for order in self:
            audit.create_event("sale_cancel", order, f"销售单已取消：{order.name}")
        return result

    def action_open_next_delivery(self):
        self.ensure_one()
        action = self.env["custom.wms.flow.step"].resolve_next_action(self, trigger_key="so_to_delivery")
        if action:
            return action
        pickings = self.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing" and p.state != "cancel")
        if not pickings:
            raise UserError("当前销售单还没有可处理的出库单。")
        action = self.env.ref("stock.action_picking_tree_outgoing").sudo().read()[0]
        action["domain"] = [("id", "in", pickings.ids)]
        if len(pickings) == 1:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    def action_confirm_and_open_delivery(self):
        self.ensure_one()
        if self.state in ("draft", "sent"):
            self.action_confirm()
        return self.action_open_next_delivery()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    wms_cost_unit = fields.Monetary(
        string="成本单价",
        currency_field="currency_id",
        compute="_compute_wms_profit_metrics",
    )
    wms_cost_subtotal = fields.Monetary(
        string="成本金额",
        currency_field="currency_id",
        compute="_compute_wms_profit_metrics",
    )
    wms_margin_amount = fields.Monetary(
        string="预计毛利",
        currency_field="currency_id",
        compute="_compute_wms_profit_metrics",
    )
    wms_margin_rate = fields.Float(
        string="毛利率(%)",
        compute="_compute_wms_profit_metrics",
        digits=(16, 2),
    )

    @api.depends("product_id", "product_uom_id", "product_uom_qty", "price_subtotal")
    def _compute_wms_profit_metrics(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.wms_cost_unit = 0.0
                line.wms_cost_subtotal = 0.0
                line.wms_margin_amount = 0.0
                line.wms_margin_rate = 0.0
                continue

            product = line.product_id
            unit_cost = product.standard_price or product.product_tmpl_id.declared_value or 0.0
            if line.product_uom_id and product.uom_id and line.product_uom_id != product.uom_id:
                unit_cost = product.uom_id._compute_price(unit_cost, line.product_uom_id)

            cost_subtotal = unit_cost * line.product_uom_qty
            margin_amount = line.price_subtotal - cost_subtotal
            margin_rate = (margin_amount / line.price_subtotal * 100.0) if line.price_subtotal else 0.0

            line.wms_cost_unit = unit_cost
            line.wms_cost_subtotal = cost_subtotal
            line.wms_margin_amount = margin_amount
            line.wms_margin_rate = margin_rate
