from odoo import api, models


class WmsLanguageDefaults(models.AbstractModel):
    _name = "custom.wms.language.defaults"
    _description = "WMS Language Defaults"

    @api.model
    def apply_defaults(self):
        target_lang = "zh_CN"

        lang_model = self.env["res.lang"].with_context(active_test=False)
        lang = lang_model.search([("code", "=", target_lang)], limit=1)
        if lang and not lang.active:
            lang.active = True
        elif not lang:
            self.env["res.lang"]._create_lang(target_lang)

        self.env["ir.default"].set("res.partner", "lang", target_lang)

        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin_user and admin_user.partner_id:
            admin_user.partner_id.lang = target_lang

        company_partner = self.env.company.partner_id
        if company_partner:
            company_partner.lang = target_lang

        return True
