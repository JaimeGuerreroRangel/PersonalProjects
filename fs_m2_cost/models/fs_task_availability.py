from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

class SaleOrder(models.Model):
    _inherit = "project.task"


    def action_fs_open_availability_task(self):
        """Abre la vista de planeación de tareas FS en una ventana modal."""
        self.ensure_one()

        # OJO: reemplaza el XML ID de la acción por el de tu menú
        # "Planeación por usuario". Lo sacas desde Depurador > Editar acción.
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "industry_fsm.project_task_action_fsm_planning_groupby_user2"  # <-- cambia este xml_id si no coincide
        )

        # Mostrarla como popup y pasar info de la OV en el contexto
        action.update({
            "target": "new",  # ventana emergente
            "context": dict(self.env.context, active_id=self.id, active_model="project.task"),
        })
        return action