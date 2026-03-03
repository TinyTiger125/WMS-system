import base64
import io
from datetime import datetime, time, timedelta

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CustomCustomsExportWizard(models.TransientModel):
    _name = "custom.customs.export.wizard"
    _description = "Customs Export Wizard"

    date_from = fields.Date()
    date_to = fields.Date()
    picking_ids = fields.Many2many(
        "stock.picking",
        string="Outbound Pickings",
        domain="[('picking_type_code', '=', 'outgoing'), ('state', '=', 'done')]",
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        if self.env.context.get("active_model") == "stock.picking" and self.env.context.get("active_ids"):
            values["picking_ids"] = [(6, 0, self.env.context["active_ids"])]
        return values

    def action_load_pickings_by_date(self):
        self.ensure_one()
        domain = [("picking_type_code", "=", "outgoing"), ("state", "=", "done")]
        if self.date_from:
            start_dt = datetime.combine(self.date_from, time.min)
            domain.append(("date_done", ">=", fields.Datetime.to_string(start_dt)))
        if self.date_to:
            end_dt = datetime.combine(self.date_to, time.min) + timedelta(days=1)
            domain.append(("date_done", "<", fields.Datetime.to_string(end_dt)))
        self.picking_ids = self.env["stock.picking"].search(domain, order="date_done asc")

    def _get_target_pickings(self):
        self.ensure_one()
        if self.picking_ids:
            return self.picking_ids
        domain = [("picking_type_code", "=", "outgoing"), ("state", "=", "done")]
        if self.date_from:
            start_dt = datetime.combine(self.date_from, time.min)
            domain.append(("date_done", ">=", fields.Datetime.to_string(start_dt)))
        if self.date_to:
            end_dt = datetime.combine(self.date_to, time.min) + timedelta(days=1)
            domain.append(("date_done", "<", fields.Datetime.to_string(end_dt)))
        return self.env["stock.picking"].search(domain, order="date_done asc")

    def _validate_pickings_for_customs(self, pickings):
        missing_lines = []
        for picking in pickings:
            for move in picking.move_ids.filtered(lambda m: m.quantity > 0 and m.product_id.type != "service"):
                tmpl = move.product_id.product_tmpl_id
                if tmpl.customs_ready:
                    continue
                missing_lines.append(
                    f"{picking.name} / {move.product_id.display_name}：{tmpl.customs_missing_fields or '报关资料不完整'}"
                )

        if missing_lines:
            sample = "\n".join(missing_lines[:20])
            if len(missing_lines) > 20:
                sample += f"\n... 其余 {len(missing_lines) - 20} 条已省略"
            raise ValidationError("报关资料缺失，无法导出。\n" + sample)

    def action_generate_xlsx(self):
        self.ensure_one()
        pickings = self._get_target_pickings()
        if not pickings:
            raise ValidationError("未找到可导出的已完成销售出库单。")
        self._validate_pickings_for_customs(pickings)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Customs Export")

        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        cell_fmt = workbook.add_format({"border": 1})
        money_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        qty_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.000"})

        headers = [
            "Done Date",
            "Picking",
            "Customer",
            "SKU",
            "Product",
            "HS Code",
            "Customs Name (CN)",
            "Customs Name (JP)",
            "Qty",
            "UoM",
            "Declared Currency",
            "Declared Unit Value",
            "Declared Line Total",
            "Net Weight (kg)",
            "Gross Weight (kg)",
            "Line Net Weight (kg)",
            "Line Gross Weight (kg)",
            "Origin Country",
        ]
        for col_idx, title in enumerate(headers):
            sheet.write(0, col_idx, title, header_fmt)
            sheet.set_column(col_idx, col_idx, 16)

        row = 1
        for picking in pickings:
            for move in picking.move_ids.filtered(lambda m: m.quantity > 0 and m.product_id.type != "service"):
                tmpl = move.product_id.product_tmpl_id
                qty = move.quantity
                currency = tmpl.declared_currency_id or picking.company_id.currency_id
                declared_unit = tmpl.declared_value or 0.0
                line_total = qty * declared_unit
                net_unit = tmpl.net_weight_kg or 0.0
                gross_unit = tmpl.gross_weight_kg or 0.0

                values = [
                    fields.Datetime.to_string(picking.date_done) if picking.date_done else "",
                    picking.name or "",
                    picking.partner_id.name or "",
                    move.product_id.default_code or "",
                    move.product_id.display_name or "",
                    tmpl.customs_hs_code or "",
                    tmpl.customs_name_cn or "",
                    tmpl.customs_name_jp or "",
                    qty,
                    move.product_uom.name or "",
                    currency.name or "",
                    declared_unit,
                    line_total,
                    net_unit,
                    gross_unit,
                    qty * net_unit,
                    qty * gross_unit,
                    tmpl.origin_country_id.code or "",
                ]

                for col_idx, value in enumerate(values):
                    if col_idx in (8, 13, 14, 15, 16):
                        sheet.write_number(row, col_idx, value or 0.0, qty_fmt)
                    elif col_idx in (11, 12):
                        sheet.write_number(row, col_idx, value or 0.0, money_fmt)
                    else:
                        sheet.write(row, col_idx, value, cell_fmt)
                row += 1

        workbook.close()
        self.file_data = base64.b64encode(output.getvalue())
        self.file_name = f"customs_export_{fields.Date.today()}.xlsx"

        self.env["custom.wms.audit.log"].create_event(
            "customs_export",
            self,
            f"报关导出已生成：{self.file_name}",
            details={
                "picking_count": len(pickings),
                "date_from": self.date_from,
                "date_to": self.date_to,
            },
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_download_file(self):
        self.ensure_one()
        if not self.file_data:
            raise ValidationError("请先生成导出文件。")
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model={self._name}&id={self.id}&field=file_data&filename_field=file_name&download=true",
            "target": "self",
        }
