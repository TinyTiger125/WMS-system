from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class ProductTemplate(models.Model):
    _inherit = "product.template"

    customs_hs_code = fields.Char(string="HS Code", index=True)
    customs_name_cn = fields.Char(string="中文报关名")
    customs_name_jp = fields.Char(string="日文报关名")
    declared_currency_id = fields.Many2one(
        "res.currency",
        string="申报币种",
        default=lambda self: self.env.company.currency_id,
    )
    declared_value = fields.Monetary(
        string="申报价格",
        currency_field="declared_currency_id",
    )
    net_weight_kg = fields.Float(string="净重(kg)")
    gross_weight_kg = fields.Float(string="毛重(kg)")
    origin_country_id = fields.Many2one("res.country", string="产地")

    # Legacy product-entry fields from the existing customer system
    name_jp = fields.Char(string="日文名")
    brand_name = fields.Char(string="品牌名称")
    manufacturer_name = fields.Char(string="生产厂家")
    spec_text = fields.Char(string="规格")
    ingredient_text = fields.Text(string="成分")
    cainiao_product_id = fields.Char(string="菜鸟商品ID", index=True)
    carton_spec = fields.Char(string="箱规")
    unit_1 = fields.Char(string="单位1")
    unit_2 = fields.Char(string="单位2")
    image_note = fields.Char(string="图片备注")
    extra_image_ids = fields.Many2many(
        "ir.attachment",
        "custom_product_template_attachment_rel",
        "product_tmpl_id",
        "attachment_id",
        string="图片组",
        domain=[("mimetype", "ilike", "image/")],
    )
    remark = fields.Text(string="备注")
    wms_min_qty = fields.Float(string="最低库存预警")
    wms_max_qty = fields.Float(string="最高库存预警")
    customs_ready = fields.Boolean(string="报关资料完整", compute="_compute_customs_ready", store=True)
    customs_missing_fields = fields.Char(string="报关缺失字段", compute="_compute_customs_ready", store=True)

    jp_customs_category_id = fields.Many2one(
        "custom.customs.category",
        string="日本海关分类",
        domain="[('category_type', '=', 'jp'), ('active', '=', True)]",
    )
    jp_customs_code = fields.Char(
        string="日本海关分类编码",
        related="jp_customs_category_id.code",
        store=True,
        readonly=True,
    )
    cn_customs_category_id = fields.Many2one(
        "custom.customs.category",
        string="中国海关分类",
        domain="[('category_type', '=', 'cn'), ('active', '=', True)]",
    )
    cn_customs_code = fields.Char(
        string="中国海关分类编码",
        related="cn_customs_category_id.code",
        store=True,
        readonly=True,
    )

    @api.depends(
        "customs_hs_code",
        "customs_name_cn",
        "declared_value",
        "origin_country_id",
        "net_weight_kg",
        "gross_weight_kg",
    )
    def _compute_customs_ready(self):
        for record in self:
            missing = []
            if not record.customs_hs_code:
                missing.append("HS Code")
            if not record.customs_name_cn:
                missing.append("中文报关名")
            if record.declared_value <= 0:
                missing.append("申报价格")
            if not record.origin_country_id:
                missing.append("产地")
            if record.net_weight_kg <= 0:
                missing.append("净重")
            if record.gross_weight_kg <= 0:
                missing.append("毛重")

            record.customs_ready = not missing
            record.customs_missing_fields = "、".join(missing)

    @api.constrains("declared_value", "net_weight_kg", "gross_weight_kg")
    def _check_non_negative_customs_values(self):
        for record in self:
            if record.declared_value < 0:
                raise ValidationError("申报价格必须大于或等于 0。")
            if record.net_weight_kg < 0:
                raise ValidationError("净重必须大于或等于 0。")
            if record.gross_weight_kg < 0:
                raise ValidationError("毛重必须大于或等于 0。")

    @api.constrains("net_weight_kg", "gross_weight_kg")
    def _check_weight_consistency(self):
        for record in self:
            if record.gross_weight_kg and record.net_weight_kg and record.gross_weight_kg < record.net_weight_kg:
                raise ValidationError("毛重不能小于净重。")

    @api.constrains("barcode")
    def _check_unique_barcode(self):
        for record in self.filtered("barcode"):
            duplicate_count = self.with_context(active_test=False).search_count(
                [("id", "!=", record.id), ("barcode", "=", record.barcode)]
            )
            if duplicate_count:
                raise ValidationError("条码必须唯一，当前条码已被其他商品使用。")

    @api.constrains("wms_min_qty", "wms_max_qty")
    def _check_stock_thresholds(self):
        for record in self:
            if record.wms_min_qty < 0:
                raise ValidationError("最低库存预警不能小于 0。")
            if record.wms_max_qty < 0:
                raise ValidationError("最高库存预警不能小于 0。")
            if record.wms_max_qty and record.wms_min_qty and record.wms_max_qty < record.wms_min_qty:
                raise ValidationError("最高库存预警不能小于最低库存预警。")

    @staticmethod
    def _normalize_audit_value(value):
        if isinstance(value, models.BaseModel):
            return value.display_name
        return value

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        history_model = self.env["custom.wms.price.history"]
        for record in records:
            if record.list_price:
                history_model.log_change(
                    product_tmpl=record,
                    change_type="sale",
                    old_value=0.0,
                    new_value=record.list_price,
                    currency=record.currency_id,
                    source_model=self._name,
                    source_ref=record.display_name,
                    note="新建商品初始化销售价",
                )
            if record.declared_value:
                history_model.log_change(
                    product_tmpl=record,
                    change_type="declared",
                    old_value=0.0,
                    new_value=record.declared_value,
                    currency=record.declared_currency_id,
                    source_model=self._name,
                    source_ref=record.display_name,
                    note="新建商品初始化申报价",
                )

        self.env["custom.wms.stock.exception"].refresh_exceptions()
        return records

    def write(self, vals):
        price_fields = {"list_price", "declared_value"}
        audit_fields = {
            "name",
            "name_jp",
            "barcode",
            "origin_country_id",
            "spec_text",
            "customs_hs_code",
            "customs_name_cn",
            "customs_name_jp",
            "wms_min_qty",
            "wms_max_qty",
        }

        old_values = {}
        for record in self:
            old_values[record.id] = {
                "list_price": record.list_price,
                "declared_value": record.declared_value,
                **{field_name: self._normalize_audit_value(record[field_name]) for field_name in audit_fields},
            }

        result = super().write(vals)

        history_model = self.env["custom.wms.price.history"]
        audit_model = self.env["custom.wms.audit.log"]
        for record in self:
            old_val = old_values.get(record.id, {})
            if "list_price" in vals:
                history_model.log_change(
                    product_tmpl=record,
                    change_type="sale",
                    old_value=old_val.get("list_price", 0.0),
                    new_value=record.list_price,
                    currency=record.currency_id,
                    source_model=self._name,
                    source_ref=record.display_name,
                    note="商品销售价修改",
                )
            if "declared_value" in vals:
                history_model.log_change(
                    product_tmpl=record,
                    change_type="declared",
                    old_value=old_val.get("declared_value", 0.0),
                    new_value=record.declared_value,
                    currency=record.declared_currency_id,
                    source_model=self._name,
                    source_ref=record.display_name,
                    note="商品申报价修改",
                )

            changed_details = {}
            for field_name in audit_fields.intersection(vals.keys()):
                old_value = old_val.get(field_name)
                new_value = self._normalize_audit_value(record[field_name])
                if old_value != new_value:
                    changed_details[field_name] = {"old": old_value, "new": new_value}
            if changed_details:
                audit_model.create_event("product_update", record, f"商品资料更新：{record.display_name}", details=changed_details)

        if {"wms_min_qty", "wms_max_qty"}.intersection(vals.keys()):
            self.env["custom.wms.stock.exception"].refresh_exceptions()

        return result

    def action_open_procurement_step(self):
        self.ensure_one()
        action = self.env["custom.wms.flow.step"].resolve_next_action(self, trigger_key="product_to_purchase")
        if not action:
            action = self.env.ref("custom_wms_base.action_custom_wms_purchase_flow").sudo().read()[0]
        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = safe_eval(action_context)
        context = {
            "default_order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product_variant_id.id,
                        "name": self.display_name,
                        "product_qty": 1.0,
                    },
                )
            ]
        }
        action["context"] = {**action_context, **context}
        return action

    def action_open_sales_step(self):
        self.ensure_one()
        action = self.env["custom.wms.flow.step"].resolve_next_action(self, trigger_key="product_to_sales")
        if not action:
            action = self.env.ref("custom_wms_base.action_custom_wms_sales_flow").sudo().read()[0]
        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = safe_eval(action_context)
        context = {
            "default_order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product_variant_id.id,
                        "name": self.display_name,
                        "product_uom_qty": 1.0,
                    },
                )
            ]
        }
        action["context"] = {**action_context, **context}
        return action
