from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    wms_stage = fields.Char(string="业务阶段", compute="_compute_wms_stage")
    wms_next_step = fields.Char(string="建议下一步", compute="_compute_wms_stage")

    @api.depends("state")
    def _compute_wms_stage(self):
        stage_map = {
            "draft": ("待确认采购单", "补齐供应商与商品明细后，点击“确认并进入入库”。"),
            "sent": ("待确认采购单", "确认采购后，系统会自动生成采购入库任务。"),
            "to approve": ("待审批采购单", "审批通过后进入采购执行与入库环节。"),
            "purchase": ("采购执行中", "进入“采购入库”核验实收数量并完成入库。"),
            "done": ("采购已完成", "可进入销售下单或复核库存变化。"),
            "cancel": ("采购已取消", "如需继续，请复制或重新创建采购单。"),
        }
        for order in self:
            stage, next_step = stage_map.get(order.state, ("未知阶段", "请联系管理员检查流程配置。"))
            order.wms_stage = stage
            order.wms_next_step = next_step

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
            action_context = action.get("context") or {}
            if isinstance(action_context, str):
                action_context = safe_eval(action_context)
            action["context"] = {**action_context, "create": False, "default_picking_type_code": "incoming"}
            return action
        pickings = self.picking_ids.filtered(lambda p: p.picking_type_code == "incoming" and p.state != "cancel")
        if not pickings:
            raise UserError("当前采购单还没有可处理的入库单。")
        action = self.env.ref("stock.action_picking_tree_incoming").sudo().read()[0]
        action["domain"] = [("id", "in", pickings.ids)]
        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = safe_eval(action_context)
        action["context"] = {**action_context, "create": False, "default_picking_type_code": "incoming"}
        if len(pickings) == 1:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    def action_confirm_and_open_receipt(self):
        self.ensure_one()
        if self.state in ("draft", "sent", "to approve"):
            self.button_confirm()
        return self.action_open_next_receipt()

    def action_apply_recent_template(self):
        self.ensure_one()
        if self.state not in ("draft", "sent", "to approve"):
            raise UserError("仅草稿/待确认采购单可套用模板。")
        if not self.partner_id:
            raise UserError("请先选择供应商，再套用模板。")

        source_order = self.search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("partner_id", "=", self.partner_id.id),
                ("state", "in", ("purchase", "done")),
            ],
            order="date_approve desc, id desc",
            limit=1,
        )
        if not source_order:
            raise UserError("该供应商暂无历史采购模板可套用。")

        template_lines = source_order.order_line.filtered(lambda l: not l.display_type and l.product_id)
        if not template_lines:
            raise UserError("历史采购单没有可套用的商品明细。")

        new_lines = []
        for line in template_lines:
            new_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "name": line.name,
                        "product_qty": line.product_qty,
                        "product_uom_id": line.product_uom_id.id,
                        "price_unit": line.price_unit,
                        "date_planned": line.date_planned or self.date_planned,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
                    },
                )
            )
        self.order_line = [(5, 0, 0)] + new_lines
        self.env["custom.wms.audit.log"].create_event("purchase_confirm", self, f"套用历史采购模板：{source_order.name}")
        return True

    @api.model
    def action_bulk_confirm_orders(self):
        active_ids = self.env.context.get("active_ids") or []
        orders = self.browse(active_ids).filtered(lambda o: o.state in ("draft", "sent", "to approve"))
        if not orders:
            raise UserError("请选择至少一条可确认的采购单。")

        success = 0
        errors = []
        for order in orders:
            try:
                order.button_confirm()
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
                "title": "采购批量确认",
                "message": message,
                "type": "warning" if errors else "success",
                "sticky": bool(errors),
            },
        }
