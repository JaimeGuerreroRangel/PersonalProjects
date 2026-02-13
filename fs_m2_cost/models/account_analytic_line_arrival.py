from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    fs_is_arrival = fields.Boolean("Marca de llegada")
    fs_arrival_status = fields.Selection(
        [
            ('on_time', 'A tiempo'),
            ('late', 'Tarde'),
            ('no_show', 'No llegó'),
        ],
        string="Estatus llegada",
        readonly=True
    )
    fs_delay_minutes = fields.Integer(
        string="Minutos de retraso",
        readonly=True
    )

    fs_arrival_datetime = fields.Datetime(
        string="Fecha/hora de llegada"
    )
