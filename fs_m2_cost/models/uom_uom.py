# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

class UoM(models.Model):
    _inherit = 'uom.uom'

    is_box = fields.Boolean(string='Es caja')
    is_roll = fields.Boolean(string='Es rollo')