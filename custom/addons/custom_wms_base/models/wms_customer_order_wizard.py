from odoo import fields, models
from odoo.exceptions import UserError, ValidationError


class WmsCustomerOrderWizard(models.TransientModel):
    _name = "custom.wms.customer.order.wizard"
    _description = "WMS Customer Order Wizard"

    contract_line_id = fields.Many2one("custom.wms.customer.contract.line", string="合同商品", required=True)
    partner_id = fields.Many2one("res.partner", string="客户", related="contract_line_id.partner_id", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="商品", related="contract_line_id.product_tmpl_id", readonly=True)
    price_unit = fields.Float(string="合同价", related="contract_line_id.price_unit", readonly=True)
    available_qty = fields.Float(string="可用库存", related="contract_line_id.available_qty", readonly=True)
    orderable_qty = fields.Float(string="可下单数量", related="contract_line_id.orderable_qty", readonly=True)
    order_qty = fields.Float(string="本次下单数量", required=True, default=1.0)

    def action_create_sale_order(self):
        self.ensure_one()
        line = self.contract_line_id
        if not line.active or not line.contract_id.active:
            raise UserError("该合同商品已停用，无法下单。")
        if self.order_qty <= 0:
            raise ValidationError("下单数量必须大于 0。")
        if self.order_qty < line.min_order_qty:
            raise ValidationError(f"下单数量不能小于最小下单量：{line.min_order_qty}")
        if self.order_qty > line.orderable_qty:
            raise ValidationError(
                f"下单数量超过可下单数量（可用库存/合同额度限制）：{line.orderable_qty}"
            )

        order = self.env["sale.order"].create(
            {
                "partner_id": line.partner_id.id,
                "wms_customer_contract_id": line.contract_id.id,
            }
        )
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": line.product_id.id,
                "product_uom_qty": self.order_qty,
                "price_unit": line.price_unit,
                "wms_customer_contract_line_id": line.id,
                "name": line.product_tmpl_id.display_name,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "我的销售订单",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }

