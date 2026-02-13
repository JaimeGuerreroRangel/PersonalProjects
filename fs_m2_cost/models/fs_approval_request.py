from odoo import fields, models

class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    fs_task_id = fields.Many2one(
        "project.task",
        string="Tarea Field Service",
        index=True,
    )
