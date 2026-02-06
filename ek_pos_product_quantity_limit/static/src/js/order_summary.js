import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(OrderSummary.prototype, {
    async _setValue(val) {
        return await super._setValue(...arguments);
    },
});
