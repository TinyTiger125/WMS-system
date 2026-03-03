from odoo import api, fields, models


class CustomWmsPriceHistory(models.Model):
    _name = "custom.wms.price.history"
    _description = "WMS Price History"
    _order = "changed_at desc, id desc"

    product_tmpl_id = fields.Many2one("product.template", string="商品", required=True, ondelete="cascade", index=True)
    change_type = fields.Selection(
        [
            ("sale", "销售价"),
            ("cost", "成本价"),
            ("declared", "申报价"),
        ],
        required=True,
        index=True,
    )
    old_value = fields.Float(string="旧值")
    new_value = fields.Float(string="新值", required=True)
    currency_id = fields.Many2one("res.currency", string="币种")
    source_model = fields.Char(string="来源模型")
    source_ref = fields.Char(string="来源单据")
    note = fields.Char(string="备注")
    changed_at = fields.Datetime(string="变更时间", default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one("res.users", string="操作人", default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one("res.company", string="公司", default=lambda self: self.env.company, required=True)

    @api.model
    def log_change(self, product_tmpl, change_type, old_value, new_value, currency=None, source_model=None, source_ref=None, note=None):
        if old_value == new_value:
            return False
        return self.sudo().create(
            {
                "product_tmpl_id": product_tmpl.id,
                "change_type": change_type,
                "old_value": old_value or 0.0,
                "new_value": new_value or 0.0,
                "currency_id": (currency or product_tmpl.currency_id or self.env.company.currency_id).id,
                "source_model": source_model or product_tmpl._name,
                "source_ref": source_ref or product_tmpl.display_name,
                "note": note,
                "user_id": self.env.user.id,
                "company_id": product_tmpl.company_id.id or self.env.company.id,
            }
        )
