/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        const order = this.getOrder();
        const config = this.models["pos.config"].getFirst();

        const isEnabled = Boolean(config?.is_pos_bill_quantity_limit);
        const limitType = config?.pos_bill_quantity_limit_type || "pos";
        const maxLines = config?.pos_bill_quantity_limit;

        if (order && isEnabled && (limitType === "pos" || limitType === "both") && maxLines) {
            const currentLineCount = order.lines.length;
            if (currentLineCount >= maxLines) {
                this.dialog.add(AlertDialog, {
                    title: _t("Limit of product Exceeded"),
                    body: _t("Can not add more than %s Products", maxLines),
                });
                return;
            }
        }

        return await super.addLineToCurrentOrder(...arguments);
    },
});
