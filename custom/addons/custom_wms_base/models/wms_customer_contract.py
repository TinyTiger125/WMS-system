from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class WmsCustomerContract(models.Model):
    _name = "custom.wms.customer.contract"
    _description = "WMS Customer Framework Contract"
    _order = "id desc"

    name = fields.Char(string="合同名称", required=True)
    partner_id = fields.Many2one("res.partner", string="客户", required=True, index=True)
    active = fields.Boolean(string="启用", default=True)
    date_start = fields.Date(string="生效日期")
    date_end = fields.Date(string="到期日期")
    note = fields.Text(string="备注")
    user_ids = fields.Many2many(
        "res.users",
        "custom_wms_contract_user_rel",
        "contract_id",
        "user_id",
        string="授权客户账号",
        help="只有这里授权的客户账号，才能查看本合同商品库存并下单。",
    )
    line_ids = fields.One2many("custom.wms.customer.contract.line", "contract_id", string="合同商品")
    line_count = fields.Integer(string="商品数", compute="_compute_line_count")

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError("到期日期不能早于生效日期。")

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_view_lines(self):
        self.ensure_one()
        action = self.env.ref("custom_wms_base.action_custom_wms_customer_contract_line").read()[0]
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {
            "default_contract_id": self.id,
        }
        return action


class WmsCustomerContractLine(models.Model):
    _name = "custom.wms.customer.contract.line"
    _description = "WMS Customer Contract Product Line"
    _order = "id desc"

    contract_id = fields.Many2one(
        "custom.wms.customer.contract", string="所属合同", required=True, ondelete="cascade", index=True
    )
    partner_id = fields.Many2one("res.partner", string="客户", related="contract_id.partner_id", store=True, index=True)
    product_tmpl_id = fields.Many2one("product.template", string="商品", required=True, index=True)
    product_id = fields.Many2one("product.product", string="商品变体", compute="_compute_product_id", store=True, index=True)
    price_unit = fields.Float(string="合同价", required=True, default=0.0)
    min_order_qty = fields.Float(string="单次最小下单量", default=1.0)
    max_order_qty = fields.Float(string="合同总量上限", default=0.0, help="0 表示不限制。")
    ordered_qty = fields.Float(string="已下单量", compute="_compute_ordered_qty")
    remaining_qty = fields.Float(string="剩余额度", compute="_compute_remaining_qty")
    available_qty = fields.Float(string="可用库存", compute="_compute_available_qty")
    orderable_qty = fields.Float(string="可下单数量", compute="_compute_orderable_qty")
    active = fields.Boolean(string="启用", default=True)

    _sql_constraints = [
        ("wms_contract_line_min_qty_nonneg", "CHECK (min_order_qty >= 0)", "最小下单量不能为负数。"),
        ("wms_contract_line_max_qty_nonneg", "CHECK (max_order_qty >= 0)", "合同总量上限不能为负数。"),
    ]

    @api.constrains("min_order_qty", "max_order_qty")
    def _check_qty_range(self):
        for rec in self:
            if rec.max_order_qty and rec.min_order_qty > rec.max_order_qty:
                raise ValidationError("单次最小下单量不能大于合同总量上限。")

    @api.depends("product_tmpl_id")
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = rec.product_tmpl_id.product_variant_id

    def _compute_ordered_qty(self):
        grouped = self.env["sale.order.line"].read_group(
            [("wms_customer_contract_line_id", "in", self.ids), ("order_id.state", "in", ("sale", "done"))],
            ["wms_customer_contract_line_id", "product_uom_qty:sum"],
            ["wms_customer_contract_line_id"],
        )
        qty_map = {item["wms_customer_contract_line_id"][0]: item["product_uom_qty"] for item in grouped}
        for rec in self:
            rec.ordered_qty = qty_map.get(rec.id, 0.0)

    @api.depends("max_order_qty", "ordered_qty")
    def _compute_remaining_qty(self):
        for rec in self:
            if rec.max_order_qty <= 0:
                rec.remaining_qty = 0.0
            else:
                rec.remaining_qty = max(rec.max_order_qty - rec.ordered_qty, 0.0)

    @api.depends("product_tmpl_id")
    def _compute_available_qty(self):
        for rec in self:
            rec.available_qty = rec.product_tmpl_id.qty_available if rec.product_tmpl_id else 0.0

    @api.depends("available_qty", "max_order_qty", "remaining_qty")
    def _compute_orderable_qty(self):
        for rec in self:
            if rec.max_order_qty > 0:
                rec.orderable_qty = max(min(rec.available_qty, rec.remaining_qty), 0.0)
            else:
                rec.orderable_qty = max(rec.available_qty, 0.0)

    def action_open_order_wizard(self):
        self.ensure_one()
        if not self.active or not self.contract_id.active:
            raise UserError("该合同商品已停用，无法下单。")
        return {
            "type": "ir.actions.act_window",
            "name": "客户下单",
            "res_model": "custom.wms.customer.order.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_contract_line_id": self.id,
            },
        }

