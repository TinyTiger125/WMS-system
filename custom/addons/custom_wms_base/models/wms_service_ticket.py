from odoo import fields, models


class CustomWmsServiceTicket(models.Model):
    _name = "custom.wms.service.ticket"
    _description = "WMS Service Ticket"
    _order = "priority desc, deadline asc, id desc"

    name = fields.Char(string="工单标题", required=True)
    partner_id = fields.Many2one("res.partner", string="客户")
    source_type = fields.Selection(
        [("sale", "销售相关"), ("purchase", "采购相关"), ("stock", "库存相关"), ("other", "其他")],
        string="来源类型",
        default="sale",
        required=True,
    )
    state = fields.Selection(
        [("new", "新建"), ("in_progress", "处理中"), ("pending", "待客户"), ("done", "已完成"), ("cancel", "已取消")],
        string="状态",
        default="new",
        required=True,
        index=True,
    )
    priority = fields.Selection(
        [("0", "低"), ("1", "中"), ("2", "高"), ("3", "紧急")],
        string="优先级",
        default="1",
        required=True,
    )
    responsible_id = fields.Many2one("res.users", string="负责人", default=lambda self: self.env.user, required=True)
    deadline = fields.Date(string="截止日期")
    description = fields.Text(string="问题描述")
    company_id = fields.Many2one("res.company", string="公司", default=lambda self: self.env.company, required=True, index=True)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_pending(self):
        self.write({"state": "pending"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancel"})
