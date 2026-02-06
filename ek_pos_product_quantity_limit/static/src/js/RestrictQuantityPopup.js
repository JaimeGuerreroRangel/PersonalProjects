/** @odoo-module **/

// import { SelectionPopup } from "@point_of_sale/static/src/app/store/selection_popup";
// import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrderline.prototype, {
    setQuantity(quantity, keep_price) {
        const config = this.config;
        const isEnabled = Boolean(config?.product_quantity_limit);
        const limitType = config?.product_quantity_limit_type || "pos";

        const checkLimit = Boolean(this.product_id?.is_product_quantity_limit);
        const maxQty = this.product_id?.limit_quantity || 0;

        const quant =
            typeof quantity === "number" ? quantity : parseFloat("" + (quantity ? quantity : 0));

        if (
            isEnabled &&
            (limitType === "pos" || limitType === "both") &&
            checkLimit &&
            maxQty > 0 &&
            quant > maxQty
        ) {
            return {
                title: _t("Quantity Limit Exceeded"),
                body: _t("Can not add more than %s piece for %s", maxQty, this.product_id.display_name),
            };
        }

        return super.setQuantity(...arguments);
    },
});

export class RestrictQuantityPopup extends Component { }
RestrictQuantityPopup.template = 'RestrictQuantityPopup';
export default RestrictQuantityPopup;
