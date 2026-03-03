from odoo import fields, models


class CustomCustomsCategory(models.Model):
    _name = "custom.customs.category"
    _description = "Customs Category Dictionary"
    _order = "category_type, name, id"

    name = fields.Char(string="分类名称", required=True, index=True)
    category_type = fields.Selection(
        [("jp", "日本海关分类"), ("cn", "中国海关分类")],
        string="分类类型",
        required=True,
        default="jp",
        index=True,
    )
    code = fields.Char(string="海关编码", required=True, index=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string="备注")

    _uniq_type_name = models.Constraint(
        "unique(category_type, name)",
        "同一分类类型下，分类名称必须唯一。",
    )
    _uniq_type_code = models.Constraint(
        "unique(category_type, code)",
        "同一分类类型下，海关编码必须唯一。",
    )
