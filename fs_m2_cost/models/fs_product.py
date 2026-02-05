from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class ProductTemplate(models.Model):
    _inherit = "product.template"

    fs_specialty_id = fields.Many2one(
        "field.service.specialty",
        string="Especialidad relacionada",
        help="Especialidad requerida para este servicio.",
    )
    fs_service_type_id = fields.Many2one(
        "field.service.type",
        string="Tipo de servicio FS",
        help="Tipo de servicio usado para las tareas de Field Service generadas desde este producto.",
    )
    
    fs_material_template_id = fields.Many2one(
        "product.template",
        string="Material relacionado",
        domain=[("type", "=", "consu")],
        help="Material principal sobre el que se basa el cálculo de horas.",
    )

    fs_is_installation = fields.Boolean(
        string="Es servicio de colocación",
        help="Marca este producto como servicio de colocación."
    )
    fs_is_leveling = fields.Boolean(
        string="Es servicio de nivelación",
        help="Marca este producto como servicio de nivelación."
    )
    fs_is_evaluation = fields.Boolean(
        string="Es servicio de evaluación",
        help="Marca este producto como servicio de evaluación."
    )
