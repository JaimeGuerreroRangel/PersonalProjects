# -*- coding: utf-8 -*-

import math
from odoo import _, api, fields, models
from odoo.tools import float_round

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_is_box = fields.Boolean(string='Es caja', compute='_compute_product_is_box', store=True)
    product_is_roll = fields.Boolean(string='Es rollo', compute='_compute_product_is_roll', store=True)

    @api.depends('product_id.uom_ids')
    def _compute_product_is_box(self):
        for line in self:
            if line.product_id.uom_ids:
                line.product_is_box = line.product_id.uom_ids[0].is_box

    @api.depends('product_id.uom_ids')
    def _compute_product_is_roll(self):
        for line in self:
            if line.product_id.uom_ids:
                line.product_is_roll = line.product_id.uom_ids[0].is_roll

    def _create_procurements(self, product_qty, procurement_uom, values):
        if self.product_is_roll and self.product_id.uom_ids:
            factor = self.product_id.uom_ids[0].relative_factor
            if factor:
                new_qty = float_round(self.product_uom_qty / factor, precision_digits=4)
                uom_ml = self.product_id.uom_ids[0]
                if uom_ml:
                    product_qty = new_qty
                    procurement_uom = uom_ml
                    values.update({
                        'product_uom_id': uom_ml.id,
                        'product_uom_qty': new_qty,
                    })
        elif self.product_is_box:
            if self.product_id.uom_ids:
                factor = self.product_id.uom_ids[0].relative_factor                
                if factor:
                    new_qty = math.ceil(float_round(self.product_uom_qty / factor, precision_digits=4))
                    target_uom = self.product_id.uom_ids[0]
                    product_qty = new_qty
                    procurement_uom = target_uom
                    values.update({
                        'product_uom_id': target_uom.id,
                        'product_uom_qty': new_qty,
                    })
        return super(SaleOrderLine, self)._create_procurements(product_qty, procurement_uom, values)
