from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


# ---------------------------------------------------------
# Tabulador de tarifas por servicio
# ---------------------------------------------------------
class FieldServiceRate(models.Model):
    _name = "field.service.rate"
    _description = "Tabulador de tarifas por servicio"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    service_id = fields.Many2one(
        "product.template",
        string="Servicio",
        domain=[("type", "=", "service")],
        required=True,
        tracking=True,
        
    )
    name = fields.Char(
        string="Descripción",
        compute="_compute_name",
        store=True,
        tracking=True,
        
    )
    tab_m2 = fields.Float(
        string="M2/Pieza/Rollo tabulados",
        help="Número de m2 (o pieza/rollo equivalente) para el cálculo de tarifa.",
        tracking=True,
        
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id.id,
        tracking=True,
    )
    tarifa_a = fields.Monetary(string="Tarifa A", currency_field="currency_id", tracking=True, )
    tarifa_b = fields.Monetary(string="Tarifa B", currency_field="currency_id", tracking=True, )

    tiempo_tabulado = fields.Float(
        string="Tiempo tabulado (horas)", 
        help="Tiempo estándar asignado para la instalación del tabulador.",
        tracking=True,
    )

    @api.depends("service_id", "service_id.name")
    def _compute_name(self):
        for rec in self:
            if rec.service_id:
                rec.name = rec.service_id.name
            else:
                rec.name = False
