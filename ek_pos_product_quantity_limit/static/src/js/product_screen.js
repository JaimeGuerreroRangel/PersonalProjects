import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ProductScreen.prototype, {
    async onNumpadClick(buttonValue) {
        return await super.onNumpadClick(...arguments);
    },
});
