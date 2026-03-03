from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CustomWmsFlowStep(models.Model):
    _name = "custom.wms.flow.step"
    _description = "WMS Flow Step"
    _order = "sequence asc, id asc"

    FLOW_ENTRY_MAP = {
        "product_to_purchase": {
            "source_model": "product.template",
            "trigger_key": "product_to_purchase",
            "source_states": False,
        },
        "product_to_sales": {
            "source_model": "product.template",
            "trigger_key": "product_to_sales",
            "source_states": False,
        },
        "po_to_receipt": {
            "source_model": "purchase.order",
            "trigger_key": "po_to_receipt",
            "source_states": "purchase,done",
        },
        "so_to_delivery": {
            "source_model": "sale.order",
            "trigger_key": "so_to_delivery",
            "source_states": "sale,done",
        },
        "inbound_done_to_sales": {
            "source_model": "stock.picking",
            "trigger_key": "inbound_done_to_sales",
            "source_states": "done",
        },
    }

    name = fields.Char(string="步骤名称", required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="顺序", default=10)
    flow_entry = fields.Selection(
        [
            ("product_to_purchase", "商品登记 -> 采购下单"),
            ("product_to_sales", "商品登记 -> 销售下单"),
            ("po_to_receipt", "采购下单 -> 采购入库"),
            ("so_to_delivery", "销售下单 -> 销售出库"),
            ("inbound_done_to_sales", "采购入库完成 -> 销售下单"),
        ],
        string="流程入口",
        help="优先使用业务入口配置，不需要理解技术字段。",
        index=True,
    )
    role_scope = fields.Selection(
        [
            ("all", "全部角色"),
            ("boss", "老板"),
            ("warehouse", "库管"),
            ("service", "客服"),
            ("sales", "销售"),
        ],
        string="角色范围",
        default="all",
        required=True,
        index=True,
    )
    source_model = fields.Char(string="来源模型", required=True, index=True)
    trigger_key = fields.Char(string="触发键", help="用于区分同一来源模型下的不同流程入口。")
    source_states = fields.Char(string="来源状态", help="多个状态用英文逗号分隔；为空表示所有状态。")
    action_id = fields.Many2one(
        "ir.actions.actions",
        string="目标动作",
        help="建议直接下拉选择目标动作；仅业务负责人可调整。",
    )
    action_xmlid = fields.Char(string="目标动作 XMLID", help="兼容字段：当未选择目标动作时会使用该值解析。")
    apply_all_companies = fields.Boolean(string="全部公司", default=True)
    company_id = fields.Many2one("res.company", string="公司")
    description = fields.Char(string="说明")

    def _apply_flow_entry_defaults(self):
        for record in self.filtered("flow_entry"):
            mapping = self.FLOW_ENTRY_MAP.get(record.flow_entry)
            if mapping:
                record.source_model = mapping["source_model"]
                record.trigger_key = mapping["trigger_key"]
                record.source_states = mapping["source_states"]

    @api.onchange("flow_entry")
    def _onchange_flow_entry(self):
        self._apply_flow_entry_defaults()

    @api.model
    def _action_from_xmlid(self, xmlid):
        if not xmlid:
            return self.env["ir.actions.actions"]
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return action if action and action._name.startswith("ir.actions.") else self.env["ir.actions.actions"]

    @api.onchange("action_id")
    def _onchange_action_id_set_xmlid(self):
        for record in self:
            if record.action_id:
                external_id = record.action_id.get_external_id().get(record.action_id.id)
                if external_id:
                    record.action_xmlid = external_id

    @api.constrains("action_id", "action_xmlid")
    def _check_action_target(self):
        for record in self:
            if not record.action_id and not record.action_xmlid:
                raise ValidationError("请至少配置“目标动作”或“目标动作 XMLID”其中之一。")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            flow_entry = vals.get("flow_entry")
            if flow_entry and flow_entry in self.FLOW_ENTRY_MAP:
                mapping = self.FLOW_ENTRY_MAP[flow_entry]
                vals["source_model"] = mapping["source_model"]
                vals["trigger_key"] = mapping["trigger_key"]
                vals["source_states"] = mapping["source_states"]
            if not vals.get("action_id") and vals.get("action_xmlid"):
                action = self._action_from_xmlid(vals.get("action_xmlid"))
                if action:
                    vals["action_id"] = action.id
        return super().create(vals_list)

    def write(self, vals):
        flow_entry = vals.get("flow_entry")
        if flow_entry and flow_entry in self.FLOW_ENTRY_MAP:
            mapping = self.FLOW_ENTRY_MAP[flow_entry]
            vals["source_model"] = mapping["source_model"]
            vals["trigger_key"] = mapping["trigger_key"]
            vals["source_states"] = mapping["source_states"]
        if not vals.get("action_id") and vals.get("action_xmlid"):
            action = self._action_from_xmlid(vals.get("action_xmlid"))
            if action:
                vals["action_id"] = action.id
        result = super().write(vals)
        if vals.get("action_id") and "action_xmlid" not in vals:
            for record in self.filtered("action_id"):
                external_id = record.action_id.get_external_id().get(record.action_id.id)
                if external_id:
                    super(CustomWmsFlowStep, record).write({"action_xmlid": external_id})
        return result

    @api.model
    def _infer_role(self, user=None):
        user = user or self.env.user
        if user.has_group("custom_wms_base.group_wms_boss"):
            return "boss"
        if user.has_group("custom_wms_base.group_wms_warehouse_ops"):
            return "warehouse"
        if user.has_group("custom_wms_base.group_wms_service_ops"):
            return "service"
        if user.has_group("custom_wms_base.group_wms_sales_ops"):
            return "sales"
        return "all"

    @api.model
    def _state_matched(self, source_states, state):
        if not source_states:
            return True
        allowed = {item.strip() for item in source_states.split(",") if item.strip()}
        return not allowed or state in allowed

    @api.model
    def _load_action_record(self, action):
        if not action:
            return False
        if action._name in {
            "ir.actions.act_window",
            "ir.actions.server",
            "ir.actions.client",
            "ir.actions.report",
            "ir.actions.act_url",
            "ir.actions.actions",
        }:
            return action.sudo().read()[0]
        return False

    @api.model
    def _load_action_by_xmlid(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return self._load_action_record(action)

    @api.model
    def _find_rules(self, record, role=None, trigger_key=None):
        role = role or self._infer_role(record.env.user)
        state = record._fields.get("state") and record.state or False
        company = record._fields.get("company_id") and record.company_id or record.env.company
        domain = [
            ("active", "=", True),
            ("source_model", "=", record._name),
            ("role_scope", "in", [role, "all"]),
            "|",
            ("apply_all_companies", "=", True),
            ("company_id", "=", company.id),
        ]
        if trigger_key:
            domain.append(("trigger_key", "=", trigger_key))
        else:
            domain.append(("trigger_key", "=", False))
        return self.search(domain, order="sequence asc, id asc"), state

    @api.model
    def resolve_next_action(self, record, role=None, trigger_key=None):
        rules, state = self._find_rules(record, role=role, trigger_key=trigger_key)
        if trigger_key and not rules:
            rules, state = self._find_rules(record, role=role, trigger_key=False)
        for rule in rules:
            if self._state_matched(rule.source_states, state):
                action = self._load_action_record(rule.action_id) or self._load_action_by_xmlid(rule.action_xmlid)
                if action:
                    return action
        return False
