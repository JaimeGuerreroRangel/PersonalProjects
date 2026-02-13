from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    fs_is_planning_stage = fields.Boolean(
        string="Etapa de planificación",
        help="Etapa donde el operador debe aceptar/rechazar/reprogramar.",
    )
    fs_is_backlog_stage = fields.Boolean(
        string="Backlog Field Service",
        help="Si se rechaza la tarea, se envía a esta etapa.",
    )

    fs_is_done_stage = fields.Boolean(
            string="Etapa finalizada FS",
            help="Si está marcado, esta etapa se considera como FINALIZADA para Field Service.",
    )
