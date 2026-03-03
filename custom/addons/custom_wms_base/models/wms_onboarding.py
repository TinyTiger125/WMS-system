from odoo import fields, models


class CustomWmsOnboarding(models.Model):
    _name = "custom.wms.onboarding"
    _description = "WMS Onboarding Guide"
    _order = "role_scope, step_no, id"

    name = fields.Char(string="步骤标题", required=True)
    role_scope = fields.Selection(
        [
            ("all", "通用"),
            ("boss", "老板"),
            ("warehouse", "仓库"),
            ("sales", "销售"),
        ],
        string="适用角色",
        required=True,
        default="all",
        index=True,
    )
    step_no = fields.Integer(string="步骤序号", required=True, default=10)
    operation_path = fields.Char(string="操作入口")
    operation_hint = fields.Text(string="操作说明")
    expected_result = fields.Text(string="完成标准")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_role_step", "unique(role_scope, step_no)", "同一角色下步骤序号不能重复。"),
    ]
