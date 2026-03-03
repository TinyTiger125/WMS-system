/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class WmsOnboardingSystray extends Component {
    setup() {
        this.action = useService("action");
    }

    openGuide() {
        this.action.doAction("custom_wms_base.action_custom_wms_onboarding");
    }
}

WmsOnboardingSystray.template = "custom_wms_base.WmsOnboardingSystray";

registry.category("systray").add("custom_wms_base.wms_onboarding_systray", {
    Component: WmsOnboardingSystray,
}, { sequence: 25 });
