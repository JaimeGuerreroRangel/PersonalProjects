# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_is_box = fields.Boolean(string='Es caja', compute='_compute_packaging_flags', store=True)
    product_is_roll = fields.Boolean(string='Es rollo', compute='_compute_packaging_flags', store=True)

    @api.depends('product_id.uom_ids', 'product_id.uom_ids.is_box', 'product_id.uom_ids.is_roll', 'product_id.uom_ids.relative_factor')
    def _compute_packaging_flags(self):
        for line in self:
            uom_pack = line._get_packaging_uom()
            line.product_is_box = bool(uom_pack and uom_pack.is_box)
            line.product_is_roll = bool(uom_pack and uom_pack.is_roll)

    def _get_packaging_uom(self):
        self.ensure_one()
        if not self.product_id or not self.product_id.uom_ids:
            return False
        return self.product_id.uom_ids[0]

    def _convert_qty_to_packaging(self, qty):
        self.ensure_one()
        uom_pack = self._get_packaging_uom()
        if not uom_pack or not uom_pack.relative_factor:
            return qty, False
        factor = uom_pack.relative_factor
        if uom_pack.is_roll:
            return (qty / factor), uom_pack
        if uom_pack.is_box:
            return math.ceil(qty / factor), uom_pack

        return qty, False

    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        res = []
        if self.product_id.type not in ('product', 'consu'):
            return res
        price_unit = self._get_stock_move_price_unit()
        qty = self._get_qty_procurement()
        move_dests = self.move_dest_ids or self.move_ids.move_dest_ids
        move_dests = move_dests.filtered(lambda m: m.state != 'cancel' and not m._is_purchase_return())

        if not move_dests:
            qty_to_attach = 0
            qty_to_push = self.product_qty - qty
        else:
            move_dests_initial_demand = self._get_move_dests_initial_demand(move_dests)
            qty_to_attach = move_dests_initial_demand - qty
            qty_to_push = self.product_qty - move_dests_initial_demand
        if self.product_uom_id.compare(qty_to_attach, 0.0) > 0:
            res.append(self._prepare_stock_move_vals(picking, price_unit, qty_to_attach, self.product_uom_id))
        if not self.product_uom_id.is_zero(qty_to_push):
            extra_move_vals = self._prepare_stock_move_vals(picking, price_unit, qty_to_push, self.product_uom_id)
            extra_move_vals['move_dest_ids'] = False
            res.append(extra_move_vals)
        return res