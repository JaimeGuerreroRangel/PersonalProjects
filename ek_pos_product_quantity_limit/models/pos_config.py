# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    """Inherited pos configuration setting for adding some
            fields for restricting out-of stock"""
    _inherit = 'pos.config'

    product_quantity_limit = fields.Boolean(
        string="Product Quantity Limit",
        help="Enable if you want to limit product quantity in point of sale or invoice",)

    product_quantity_limit_type = fields.Selection([('pos', 'POS'), ('both', 'POS and Invoice')],
                                                   string='Product Quantity Limit Type', default='pos',)

    is_pos_bill_quantity_limit = fields.Boolean(
        string="Enable POS Bill Quantity Limit",
        help="Enable if you want to limit quantity in point of sale bill",)

    pos_bill_quantity_limit = fields.Integer(
        string="POS Bill Quantity Limit",
        help="Enter the quantity limit for POS bill",)

    pos_bill_quantity_limit_type = fields.Selection([('pos', 'POS'), ('both', 'POS and Invoice')],
                                                string='Product Limit Type', default='pos',)
