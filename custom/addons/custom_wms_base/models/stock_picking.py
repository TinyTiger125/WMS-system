from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class StockPicking(models.Model):
    _inherit = "stock.picking"

    wms_stage = fields.Char(string="业务阶段", compute="_compute_wms_stage")
    wms_next_step = fields.Char(string="建议下一步", compute="_compute_wms_stage")

    @staticmethod
    def _has_cancel_permission(user):
        return user.has_group("base.group_system") or user.has_group("custom_wms_base.group_wms_boss")

    @api.depends("state", "picking_type_code", "origin")
    def _compute_wms_stage(self):
        for picking in self:
            flow_name = "入库" if picking.picking_type_code == "incoming" else "出库" if picking.picking_type_code == "outgoing" else "库存作业"
            if picking.state == "draft":
                stage = f"待处理{flow_name}单"
                next_step = "核对业务对象、作业场景、商品数量后点击“验证”。"
            elif picking.state in ("waiting", "confirmed"):
                stage = f"{flow_name}任务准备中"
                next_step = "等待可处理状态，建议先处理其他待办任务。"
            elif picking.state == "assigned":
                stage = f"可执行{flow_name}"
                next_step = "核对商品与数量，完成后点击“验证”。"
            elif picking.state == "done":
                stage = f"{flow_name}已完成"
                next_step = "可返回列表查看下一张任务单。"
            elif picking.state == "cancel":
                stage = f"{flow_name}已取消"
                next_step = "如需继续，请回到上游业务单重新生成任务。"
            else:
                stage = "未知阶段"
                next_step = "请联系管理员检查流程配置。"
            picking.wms_stage = stage
            picking.wms_next_step = next_step

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "picking_type_id" not in fields_list or vals.get("picking_type_id"):
            return vals

        target_code = self.env.context.get("default_picking_type_code")
        if not target_code:
            can_inbound = self.env.user.has_group("custom_wms_base.group_wms_feature_purchase_receipt")
            can_outbound = self.env.user.has_group("custom_wms_base.group_wms_feature_sales_delivery")
            if can_inbound and not can_outbound:
                target_code = "incoming"
            elif can_outbound and not can_inbound:
                target_code = "outgoing"

        if not target_code:
            return vals

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", target_code),
                ("company_id", "in", (False, self.env.company.id)),
            ],
            order="company_id desc, sequence asc, id asc",
            limit=1,
        )
        if picking_type:
            vals["picking_type_id"] = picking_type.id
        return vals

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

    def action_open_recommended_purchase(self):
        self.ensure_one()
        action = self.env.ref("custom_wms_base.action_custom_wms_purchase_flow").sudo().read()[0]
        base_context = action.get("context") or {}
        if isinstance(base_context, str):
            base_context = safe_eval(base_context)
        action["context"] = {
            **base_context,
            "default_partner_id": self.partner_id.id or False,
        }
        return action

    def action_open_recommended_sales(self):
        self.ensure_one()
        action = self.env.ref("custom_wms_base.action_custom_wms_sales_flow").sudo().read()[0]
        base_context = action.get("context") or {}
        if isinstance(base_context, str):
            base_context = safe_eval(base_context)
        action["context"] = {
            **base_context,
            "default_partner_id": self.partner_id.id or False,
        }
        return action

    def action_back_to_operation_list(self):
        self.ensure_one()
        if self.picking_type_code == "incoming":
            action_xmlid = "custom_wms_base.action_custom_wms_receipts_flow"
        elif self.picking_type_code == "outgoing":
            action_xmlid = "custom_wms_base.action_custom_wms_deliveries_flow"
        else:
            action_xmlid = "stock.action_picking_tree_all"
        return self.env.ref(action_xmlid).sudo().read()[0]
