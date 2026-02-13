from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    def write(self, vals):
        # ============================
        # 1) Bloquear retroceso de etapa
        # ============================
        if "stage_id" in vals:
            new_stage = self.env["project.task.type"].browse(vals["stage_id"])
            if new_stage:
                # Solo estos usuarios podrán retroceder etapas
                # (puedes cambiar el grupo por uno propio si quieres)
                can_move_back = self.env.user.has_group("industry_fsm.group_fsm_manager")

                for task in self:
                    old_stage = task.stage_id
                    # Validamos que haya etapa anterior y que ambas tengan secuencia
                    if (
                        old_stage
                        and old_stage.sequence
                        and new_stage.sequence
                        and new_stage.sequence < old_stage.sequence  # 👉 etapa "hacia atrás"
                        and not can_move_back
                    ):
                        raise UserError(_(
                            "No tienes permisos para retroceder la etapa de la tarea '%s'."
                        ) % task.display_name)
        res = super().write(vals)
        return res

