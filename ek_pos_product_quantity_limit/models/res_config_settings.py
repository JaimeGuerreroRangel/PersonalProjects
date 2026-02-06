# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """
    This is an Odoo model for configuration settings. It inherits from the
    'res.config.settings' model and extends its functionality by adding
    fields for low stock alert configuration

    """
    _inherit = 'res.config.settings'

    product_quantity_limit = fields.Boolean(
        string="Product Quantity Limit",
        help="Enable if you want to limit product quantity in point of sale or invoice",
        related='pos_config_id.product_quantity_limit',
        readonly=False, store=True, config_parameter='ek_pos_product_quantity_limit.product_quantity_limit')

    product_quantity_limit_type = fields.Selection([('pos', 'POS'), ('both', 'POS and Invoice')],
                                                   string='Product Quantity Limit Type', default='pos',
                                                   related='pos_config_id.product_quantity_limit_type',
                                                   readonly=False, store=True,
                                                   config_parameter='ek_pos_product_quantity_limit.product_quantity_limit_type')

    is_pos_bill_quantity_limit = fields.Boolean(
        string="Enable POS Bill Quantity Limit",
        help="Enable if you want to limit quantity in point of sale bill",
        related='pos_config_id.is_pos_bill_quantity_limit', 
        readonly=False, store=True ,config_parameter='ek_pos_product_quantity_limit.is_pos_bill_quantity_limit'
    )
    pos_bill_quantity_limit = fields.Integer(
        string="POS Bill Quantity Limit",
        help="Enter the quantity limit for POS bill",
        related='pos_config_id.pos_bill_quantity_limit', 
        readonly=False, store=True , config_parameter='ek_pos_product_quantity_limit.pos_bill_quantity_limit'
    )

    pos_bill_quantity_limit_type = fields.Selection([('pos', 'POS'), ('both', 'POS and Invoice')],
                                                   string='Bill Quantity Limit Type', default='pos',
                                                   related='pos_config_id.pos_bill_quantity_limit_type',
                                                   readonly=False, store=True,
                                                   config_parameter='ek_pos_product_quantity_limit.pos_bill_quantity_limit_type')
