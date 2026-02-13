from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


# ---------------------------------------------------------
# Especialidades
# ---------------------------------------------------------
class FieldServiceSpecialty(models.Model):
    _name = "field.service.specialty"
    _description = "Especialidad de Field Service"
    _order = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Nombre de especialidad", required=True)
    create_date = fields.Datetime(string="Fecha de creación", readonly=True)
    create_uid = fields.Many2one(
        "res.users",
        string="Creado por",
        readonly=True,
        tracking=True,
    )