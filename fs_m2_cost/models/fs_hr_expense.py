from odoo import fields, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    task_id = fields.Many2one(
        "project.task",
        string="Tarea Field Service",
        help="Tarea asociada a este gasto.",
    )
