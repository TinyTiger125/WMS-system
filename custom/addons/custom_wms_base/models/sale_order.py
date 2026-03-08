from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class SaleOrder(models.Model):
    _inherit = "sale.order"

    wms_stage = fields.Char(string="业务阶段", compute="_compute_wms_stage")
    wms_next_step = fields.Char(string="建议下一步", compute="_compute_wms_stage")

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
    wms_customer_contract_id = fields.Many2one("custom.wms.customer.contract", string="客户框架合同", index=True)

    @staticmethod
    def _has_cancel_permission(user):
        return user.has_group("base.group_system") or user.has_group("custom_wms_base.group_wms_boss")

    @api.depends("state")
    def _compute_wms_stage(self):
        stage_map = {
            "draft": ("待确认销售单", "确认客户、商品、价格后点击“确认并进入出库”。"),
            "sent": ("待客户确认", "确认后将自动生成销售出库任务。"),
            "sale": ("销售执行中", "进入“销售出库”完成拣货、复核与出库。"),
            "done": ("销售已完成", "可查看利润与回款状态。"),
            "cancel": ("销售已取消", "如需继续，请复制或重新创建销售单。"),
        }
        for order in self:
            stage, next_step = stage_map.get(order.state, ("未知阶段", "请联系管理员检查流程配置。"))
            order.wms_stage = stage
            order.wms_next_step = next_step

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
            action_context = action.get("context") or {}
            if isinstance(action_context, str):
                action_context = safe_eval(action_context)
            action["context"] = {**action_context, "create": False, "default_picking_type_code": "outgoing"}
            return action
        pickings = self.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing" and p.state != "cancel")
        if not pickings:
            raise UserError("当前销售单还没有可处理的出库单。")
        action = self.env.ref("stock.action_picking_tree_outgoing").sudo().read()[0]
        action["domain"] = [("id", "in", pickings.ids)]
        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = safe_eval(action_context)
        action["context"] = {**action_context, "create": False, "default_picking_type_code": "outgoing"}
        if len(pickings) == 1:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    def action_confirm_and_open_delivery(self):
        self.ensure_one()
        if self.state in ("draft", "sent"):
            self.action_confirm()
        return self.action_open_next_delivery()

    def action_apply_recent_template(self):
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError("仅草稿/待确认销售单可套用模板。")
        if not self.partner_id:
            raise UserError("请先选择客户，再套用模板。")

        source_order = self.search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("partner_id", "=", self.partner_id.id),
                ("state", "in", ("sale", "done")),
            ],
            order="date_order desc, id desc",
            limit=1,
        )
        if not source_order:
            raise UserError("该客户暂无历史销售模板可套用。")

        template_lines = source_order.order_line.filtered(lambda l: not l.display_type and l.product_id)
        if not template_lines:
            raise UserError("历史销售单没有可套用的商品明细。")

        new_lines = []
        for line in template_lines:
            new_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "name": line.name,
                        "product_uom_qty": line.product_uom_qty,
                        "product_uom_id": line.product_uom_id.id,
                        "price_unit": line.price_unit,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
                    },
                )
            )
        self.order_line = [(5, 0, 0)] + new_lines
        self.env["custom.wms.audit.log"].create_event("sale_confirm", self, f"套用历史销售模板：{source_order.name}")
        return True

    @api.model
    def action_bulk_confirm_orders(self):
        active_ids = self.env.context.get("active_ids") or []
        orders = self.browse(active_ids).filtered(lambda o: o.state in ("draft", "sent"))
        if not orders:
            raise UserError("请选择至少一条可确认的销售单。")

        success = 0
        errors = []
        for order in orders:
            try:
                order.action_confirm()
                success += 1
            except Exception as exc:
                errors.append(f"{order.name}: {exc}")

        message = f"批量确认完成：成功 {success} 条"
        if errors:
            message += "；失败 " + str(len(errors)) + " 条。"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "销售批量确认",
                "message": message,
                "type": "warning" if errors else "success",
                "sticky": bool(errors),
            },
        }


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
    wms_customer_contract_line_id = fields.Many2one(
        "custom.wms.customer.contract.line", string="合同商品行", index=True
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
