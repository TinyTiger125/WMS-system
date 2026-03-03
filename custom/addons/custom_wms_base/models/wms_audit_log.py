import json

from odoo import api, fields, models


class CustomWmsAuditLog(models.Model):
    _name = "custom.wms.audit.log"
    _description = "WMS Audit Log"
    _order = "event_time desc, id desc"

    event_time = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    event_type = fields.Selection(
        [
            ("product_update", "商品资料修改"),
            ("purchase_confirm", "采购单确认"),
            ("purchase_cancel", "采购单取消"),
            ("sale_confirm", "销售单确认"),
            ("sale_cancel", "销售单取消"),
            ("picking_validate", "出入库过账"),
            ("picking_cancel", "出入库取消"),
            ("customs_export", "报关导出"),
        ],
        required=True,
        index=True,
    )
    model_name = fields.Char(string="模型", required=True, index=True)
    res_id = fields.Integer(string="记录ID", index=True)
    record_display_name = fields.Char(string="业务单据")
    summary = fields.Char(string="摘要", required=True)
    detail_json = fields.Text(string="明细(JSON)")
    user_id = fields.Many2one("res.users", string="操作人", default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one("res.company", string="公司", default=lambda self: self.env.company, required=True)

    @api.model
    def create_event(self, event_type, record, summary, details=None):
        detail_json = False
        if details:
            detail_json = json.dumps(details, ensure_ascii=False, default=str)
        return self.sudo().create(
            {
                "event_type": event_type,
                "model_name": record._name,
                "res_id": record.id,
                "record_display_name": record.display_name,
                "summary": summary,
                "detail_json": detail_json,
                "user_id": self.env.user.id,
                "company_id": getattr(record, "company_id", self.env.company).id or self.env.company.id,
            }
        )
