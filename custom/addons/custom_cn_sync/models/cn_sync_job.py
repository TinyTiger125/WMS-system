import json
from datetime import timedelta

import requests

from odoo import api, fields, models


class CustomCnSyncJob(models.Model):
    _name = "custom.cn.sync.job"
    _description = "CN Sync Job"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, copy=False, default=lambda self: self.env["ir.sequence"].next_by_code("custom.cn.sync.job"))
    picking_id = fields.Many2one("stock.picking", ondelete="set null")
    direction = fields.Selection(
        [("outbound", "Outbound"), ("inbound", "Inbound")],
        default="outbound",
        required=True,
    )
    state = fields.Selection(
        [("pending", "Pending"), ("processing", "Processing"), ("done", "Done"), ("failed", "Failed")],
        default="pending",
        required=True,
        index=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    retry_count = fields.Integer(default=0)
    next_try = fields.Datetime(default=fields.Datetime.now, index=True)
    last_try = fields.Datetime()
    payload_json = fields.Text()
    response_message = fields.Text()
    error_details = fields.Text()

    @staticmethod
    def _build_payload_from_picking(picking):
        lines = []
        for move in picking.move_ids.filtered(lambda m: m.quantity > 0 and m.product_id.type != "service"):
            lines.append(
                {
                    "sku": move.product_id.default_code or "",
                    "product_name": move.product_id.display_name,
                    "qty": move.quantity,
                    "uom": move.product_uom.name,
                }
            )
        return {
            "picking": picking.name,
            "scheduled_date": str(picking.scheduled_date or ""),
            "done_date": str(picking.date_done or ""),
            "partner": picking.partner_id.name or "",
            "lines": lines,
        }

    @api.model
    def create_from_picking(self, picking):
        payload = self._build_payload_from_picking(picking)
        return self.create(
            {
                "picking_id": picking.id,
                "direction": "outbound",
                "payload_json": json.dumps(payload, ensure_ascii=False),
            }
        )

    def action_mark_pending(self):
        self.write(
            {
                "state": "pending",
                "next_try": fields.Datetime.now(),
                "error_details": False,
                "response_message": False,
            }
        )

    def action_process_now(self):
        self._process_jobs()

    @api.model
    def action_process_pending(self, limit=50):
        jobs = self.search(
            [("state", "in", ("pending", "failed")), ("next_try", "<=", fields.Datetime.now())],
            limit=limit,
            order="next_try asc, id asc",
        )
        jobs._process_jobs()

    @api.model
    def _cron_process_pending_jobs(self):
        self.action_process_pending(limit=100)

    def _process_jobs(self):
        config = self.env["custom.cn.sync.config"]._get_current_config()
        for job in self:
            max_retries = config.max_retries if config else 3
            if job.retry_count >= max_retries and job.state == "failed":
                continue
            job._process_single_job(config=config, max_retries=max_retries)

    def _process_single_job(self, config, max_retries):
        self.ensure_one()
        now = fields.Datetime.now()
        self.state = "processing"
        self.last_try = now

        try:
            if not config:
                raise RuntimeError("No enabled CN sync configuration found.")

            if config.mode == "mock":
                self.write(
                    {
                        "state": "done",
                        "response_message": f"Mock synced at {now}",
                        "error_details": False,
                        "next_try": False,
                    }
                )
                return

            if not config.endpoint_url:
                raise RuntimeError("Endpoint URL is empty.")

            payload = json.loads(self.payload_json or "{}")
            headers = {"Content-Type": "application/json"}
            if config.api_token:
                headers["Authorization"] = f"Bearer {config.api_token}"
            response = requests.post(
                config.endpoint_url,
                json=payload,
                headers=headers,
                timeout=config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

            self.write(
                {
                    "state": "done",
                    "response_message": response.text[:1000] or f"HTTP {response.status_code}",
                    "error_details": False,
                    "next_try": False,
                }
            )
        except Exception as exc:
            retry_count = self.retry_count + 1
            delay_minutes = 2 ** min(retry_count, 6)
            next_try = now + timedelta(minutes=delay_minutes)
            self.write(
                {
                    "retry_count": retry_count,
                    "state": "failed" if retry_count >= max_retries else "pending",
                    "response_message": str(exc)[:1000],
                    "error_details": str(exc),
                    "next_try": next_try,
                }
            )
