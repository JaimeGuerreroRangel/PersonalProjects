from odoo import api, fields, models, _
from odoo.exceptions import UserError  

class TaskKpiReasonWizard(models.TransientModel):
    _name = "task.kpi.reason.wizard"
    _description = "Motivo cambio tarea"

    task_id = fields.Many2one("project.task", required=True)
    reason = fields.Text("Motivo", required=True)
    reschedule_date = fields.Datetime("Fecha estimada de reprogramación")
    action_type = fields.Selection(
        [("reject", "Rechazar"), ("reschedule", "Reprogramar")],
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        if task.fs_decision_locked:
            raise UserError(_("Ya se ha tomado una decisión para esta tarea."))
        
        # ======================
        #  RECHAZAR
        # ======================
        if self.action_type == "reject":
            task.fs_status = "rejected"
            task.fs_decision_locked = True
            # Mandar a backlog
            backlog_stage = task.env["project.task.type"].search(
                [("fs_is_backlog_stage", "=", True)], limit=1
            )
            if backlog_stage:
                task.stage_id = backlog_stage
            # Registro KPI
            task._create_task_kpi_entry(
                new_status="rejected",
                reason=self.reason,
            )
            # Mensaje en chatter
            body = _(
                "La tarea ha sido <b>RECHAZADA</b> por %s.<br/>Motivo: %s"
            ) % (self.env.user.display_name, self.reason)
            task.message_post(body=body, subtype_xmlid="mail.mt_note")
            # Enviar correo al coordinador
            template = task.env.ref(
                "fs_m2_cost.mail_fs_task_rejected",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(task.id, force_send=True)
        
        # ======================
        #  REPROGRAMAR
        # ======================
        elif self.action_type == "reschedule":
            task.fs_status = "reschedule"
            task.fs_decision_locked = True
            # Registro KPI
            task._create_task_kpi_entry(
                new_status="reschedule",
                reason=self.reason,
                new_date=self.reschedule_date,
            )
            # Crear aprobación
            category = task.env.ref(
                "fs_m2_cost.approval_category_fs_reprogram",
                raise_if_not_found=False,
            )
            approval_vals = {
                "name": _("Reprogramación tarea %s") % (task.fs_sequence or task.name),
                "request_owner_id": self.env.user.id,
                "reason": self.reason,
                "date": fields.Date.today(),
                "fs_task_id": task.id,
            }
            if category:
                approval_vals["category_id"] = category.id
            approval = task.env["approval.request"].create(approval_vals)
            
            # Se combinan los coordinadores de instalación, nivelación y evaluación
            coordinators = (
                task.company_id.fs_coordinator_installation_ids
                | task.company_id.fs_coordinator_leveling_ids
                | task.company_id.fs_coordinator_evaluator_ids
            )
            
            # Crear un aprobador por cada coordinador encontrado
            if coordinators:
                for coordinator in coordinators:
                    task.env["approval.approver"].create(
                        {"request_id": approval.id, "user_id": coordinator.id}
                    )
            
            # Mensaje + enlace
            link = "%s/web#id=%s&model=approval.request&view_type=form" % (
                task.get_base_url(),
                approval.id,
            )
            body = _(
                "La tarea ha sido marcada para <b>REPROGRAMACIÓN</b> por %s.<br/>"
                "Motivo: %s<br/>"
                'Revisión de aprobación: <a href="%s">Abrir aprobación</a>'
            ) % (self.env.user.display_name, self.reason, link)
            task.message_post(body=body, subtype_xmlid="mail.mt_note")
            # Correo al coordinador, pasando el link en el contexto
            template = task.env.ref("fs_m2_cost.mail_fs_task_reschedule", raise_if_not_found=False)
            if template:
                template.with_context(approval_link=link).send_mail(task.id, force_send=True)
        
        return {"type": "ir.actions.act_window_close"}
