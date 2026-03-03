from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CustomCnSyncConfig(models.Model):
    _name = "custom.cn.sync.config"
    _description = "CN Sync Configuration"

    name = fields.Char(required=True, default="Default")
    active = fields.Boolean(default=True)
    enabled = fields.Boolean(default=True)
    mode = fields.Selection(
        [("mock", "Mock"), ("live", "Live API")],
        default="mock",
        required=True,
    )
    endpoint_url = fields.Char(string="Endpoint URL")
    api_token = fields.Char(string="API Token")
    timeout_seconds = fields.Integer(default=10)
    max_retries = fields.Integer(default=3)
    note = fields.Text()

    def _get_current_config(self):
        return self.search([("active", "=", True), ("enabled", "=", True)], limit=1)

    def action_open_pending_jobs(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("custom_cn_sync.action_custom_cn_sync_job")
        action["domain"] = [("state", "in", ("pending", "failed"))]
        return action

    @api.constrains("timeout_seconds", "max_retries")
    def _validate_positive_fields(self):
        for record in self:
            if record.timeout_seconds <= 0:
                raise ValidationError("Timeout must be greater than 0 seconds.")
            if record.max_retries < 0:
                raise ValidationError("Max Retries must be greater than or equal to 0.")
