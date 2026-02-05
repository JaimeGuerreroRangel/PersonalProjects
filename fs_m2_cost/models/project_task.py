# -*- coding: utf-8 -*-
import logging
import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'
    
    sale_user_id = fields.Many2one(
        related='sale_order_id.user_id',
        string='Vendedor',
        store=False,
        readonly=True
    )
    
    fs_service_template_id = fields.Many2one(
        'product.template',
        string='Artículo de servicio',
        domain="[('type', '=', 'service')]",
        help='Servicio a usar cuando no hay OV relacionada'
    )

    def action_download_fsm_report(self):
        """Descargar PDF generado al momento"""
        self.ensure_one()
        
        if not self._is_fsm_report_available():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("No hay suficiente datos disponibles para generar el pdf."),
                    'type': 'warning',
                },
            }
        
        # Generar y descargar directamente
        return self.env.ref('industry_fsm.task_custom_report').report_action(self)
    
    def action_fsm_reopen(self):
        """Reabrir tarea FSM completada"""
        for task in self:
            if not task.is_fsm:
                raise UserError(_("Esta acción solo está disponible para tareas de Field Service."))
            
            # Usar la etapa específica "Planeado" de FSM
            planning_stage = self.env.ref('industry_fsm.planning_project_stage_2', raise_if_not_found=False)
            
            if not planning_stage:
                # Fallback: buscar cualquier etapa abierta
                planning_stage = self.env['project.task.type'].search([
                    ('project_ids', 'in', task.project_id.ids),
                    ('fold', '=', False),
                ], order='sequence', limit=1)
            
            if not planning_stage:
                raise UserError(_("No se encontró una etapa abierta para reabrir la tarea."))
            
            # Actualizar la tarea
            task.write({
                'stage_id': planning_stage.id,
                'fsm_done': False,
                'state': '01_in_progress',
            })
            
            # Mensaje en el chatter
            task.message_post(
                body=_("Tarea reabierta por %(user)s y movida a la etapa '%(stage)s'") % {
                    'user': self.env.user.name,
                    'stage': planning_stage.name,
                },
                message_type='notification',
            )
        
        return True

    def action_timer_start(self):
        # Validación: Verificar si la tarea está completada
        if self.fsm_done:
            raise UserError(_(
                "⚠️ No se puede iniciar el timer en una tarea completada.\n\n"
                "Estado actual: Tarea Hecha\n\n"
                "Para registrar tiempo adicional:\n"
                "• Contacta a tu supervisor o administrador del proyecto\n"
                "• Solicita que reabran la tarea\n"
                "• Una vez reabierta, podrás registrar tiempo normalmente"
            ))
        
        # Si todas las validaciones pasan, continuar con el método original
        return super().action_timer_start()

    def write(self, vals):
        """Detectar cambio de etapa y ejecutar acción"""
        # Guardar etapa anterior antes de actualizar
        old_stage_ids = {task.id: task.stage_id.id for task in self}
        
        # Ejecutar el write normal
        result = super(ProjectTask, self).write(vals)
        
        # Si cambió la etapa
        if 'stage_id' in vals:
            for task in self:
                old_stage_id = old_stage_ids.get(task.id)
                new_stage_id = task.stage_id.id
                
                # Solo si realmente cambió
                if old_stage_id != new_stage_id:
                    # Aquí ejecutas tu acción
                    task._on_stage_change(old_stage_id, new_stage_id)
        
        return result
    
    def _on_stage_change(self, old_stage_id, new_stage_id):
        """Acción a ejecutar cuando cambia la etapa"""
        old_stage = self.env['project.task.type'].browse(old_stage_id)
        new_stage = self.stage_id
        
        # Obtener etapa por external ID
        validation_stage = self.env.ref('industry_fsm.planning_project_stage_1', raise_if_not_found=False)
        
        if validation_stage and new_stage.id == validation_stage.id and self.user_ids:
            self.create_validation_activity()
            
    def create_validation_activity(self):
        """Crear actividad de validación para cada usuario asignado"""
        self.ensure_one()
        
        if not self.user_ids:
            return
        
        # Tipo de actividad
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return
        
        # Crear actividad para cada usuario en user_ids
        for user in self.user_ids:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                summary=f'Asignación tarea: {self.name}',
                note=f'Se ha asignado la tarea "{self.name}" del proyecto "{self.project_id.name}"',
                user_id=user.id,
                date_deadline=fields.Date.today() + timedelta(days=1)
            )
            
    def action_fsm_validate(self, stop_running_timers=False):
        """Validar FSM y completar todas las actividades planificadas"""
        
        res = super().action_fsm_validate(stop_running_timers)
        
        # Completar actividades
        for task in self:
            if task.activity_ids:
                task.activity_ids.action_feedback()
                

        return res
    
    def action_complete_my_activities(self):
        """Completar solo las actividades del usuario actual"""
        self.ensure_one()
        
        current_user = self.env.user
        
        if self.activity_ids:
            # Filtrar actividades del usuario actual
            my_activities = self.activity_ids.filtered(
                lambda a: a.user_id == current_user
            )
            
            if my_activities:
                my_activities.action_feedback()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Actividades completadas',
                        'message': f'{len(my_activities)} actividad(es) marcada(s) como completada(s)',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Sin actividades',
                        'message': 'No tienes actividades planeadas pendientes en esta tarea',
                        'type': 'warning',
                    }
                }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin actividades',
                    'message': 'Esta tarea no tiene actividades',
                    'type': 'info',
                }
            }