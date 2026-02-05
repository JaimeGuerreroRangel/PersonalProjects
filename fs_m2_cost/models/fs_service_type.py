from odoo import api, fields, models, _

class FieldServiceType(models.Model):
    _name = "field.service.type"
    _description = "Tipo de servicio Field Service"
    _order = "name"

    name = fields.Char(
        string="Nombre",
        required=True,
        help="Nombre del tipo de servicio, por ejemplo: Colocación, Nivelación.",
    )
    code = fields.Char(
        string="Código",
        required=True,
        help="Código corto para este tipo de servicio, por ejemplo: SCO, SNV.",
    )
    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Secuencia",
        help="Secuencia usada para numerar las tareas de este tipo de servicio.",
    )
    active = fields.Boolean(default=True)
