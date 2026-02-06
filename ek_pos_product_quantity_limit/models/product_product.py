# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    """
    This is an Odoo model for product products. It inherits from the
    'product.product' model and extends its functionality by adding a
    computed field for product alert state.

     Methods:
        _compute_alert_tag(): Computes the value of the 'alert_tag' field based on the
        product's stock quantity and configured low stock alert parameters
    """
    _inherit = 'product.product'

    is_product_quantity_limit = fields.Boolean(
        string="Product Quantity Limit",
        help="Enable if you want to limit product quantity in point of sale or invoice",
        config_parameter='ek_pos_product_quantity_limit.product_quantity_limit',
        compute='_compute_is_product_quantity_limit')
    limit_quantity = fields.Float(
        string='Limit Quantity',
        help='Enter the quantity limit for product',
    )

    def _compute_is_product_quantity_limit(self):
        for rec in self:
            rec.is_product_quantity_limit = self.env['ir.config_parameter'].sudo().get_param(
                'ek_pos_product_quantity_limit.product_quantity_limit')

    
    @api.model
    def _load_pos_data_fields(self, config_id):

        fields = super(ProductProduct, self)._load_pos_data_fields(config_id)
        
        fields.append('limit_quantity')
        fields.append('is_product_quantity_limit')

        return fields