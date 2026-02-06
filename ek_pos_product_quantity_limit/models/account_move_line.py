# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('quantity', 'product_id')
    def _onchange_quantity(self):
        product_quantity_limit = self.env['ir.config_parameter'].sudo().get_param(
            'ek_pos_product_quantity_limit.product_quantity_limit')
        if product_quantity_limit:
            product_quantity_limit_type = self.env['ir.config_parameter'].sudo().get_param(
                'ek_pos_product_quantity_limit.product_quantity_limit_type')
            if product_quantity_limit_type == 'both':
                if self.product_id and self.quantity and self.product_id.limit_quantity > 0:
                    if self.quantity > self.product_id.limit_quantity:
                        raise ValidationError(_('Quantity should be less than %s for %s') % (
                            self.product_id.limit_quantity, self.product_id.display_name))
