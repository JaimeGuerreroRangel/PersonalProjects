from odoo import api, fields, models, _


class TaskKpi(models.Model):
    _name = "task.kpi"
    _description = "KPI de cambios de tarea"
    _order = "change_date asc, id asc"

    task_id = fields.Many2one(
        "project.task",
        string="Tarea",
        required=True,
        ondelete="cascade",
    )
    change_date = fields.Datetime(
        string="Fecha de modificación",
        default=fields.Datetime.now,
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        default=lambda self: self.env.user,
    )
    previous_status = fields.Char(
        string="Estatus anterior",
    )
    current_status = fields.Char(
        string="Estatus actual",
    )
    reason = fields.Text(
        string="Motivo",
    )
    reschedule_date = fields.Date(
        string="Fecha estimada de reprogramación",
    )
    change_count = fields.Integer(
        string="# de cambios",
        readonly=True,
    )
