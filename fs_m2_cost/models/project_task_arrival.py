from odoo import api, fields, models, _
from datetime import timedelta



class ProjectTask(models.Model):
    _inherit = 'project.task'

    fs_arrival_datetime = fields.Datetime(
        string="Fecha/hora de llegada",
        readonly=True
    )
    fs_arrival_status = fields.Selection(
        [
            ('on_time', 'A tiempo'),
            ('late', 'Tarde'),
            ('no_show', 'No llegó'),
        ],
        string="Estatus de llegada",
        readonly=True
    )
    fs_delay_minutes = fields.Integer(
        string="Minutos de retraso",
        readonly=True
    )

    def action_timer_start(self):
        """Se ejecuta cuando el usuario pulsa el botón 'Iniciar'."""
        res = super().action_timer_start()

        now = fields.Datetime.now()
        

        for task in self:
            # Si no hay fecha planeada, no calculamos nada
            if not task.date_deadline:
                continue
            
            tolerance = task.company_id.fs_arrival_tolerance_minutes or 0
            # Tomamos SIEMPRE esta llegada como nueva sesión
            diff_minutes = (now - task.date_deadline).total_seconds() / 60.0

            if diff_minutes <= tolerance:
                status = 'on_time'
                delay = 0
            else:
                status = 'late'
                delay = int(round(diff_minutes))

            task.write({
                'fs_arrival_datetime': now,
                'fs_arrival_status': status,
                'fs_delay_minutes': delay,
            })

        return res

    def action_timer_stop(self):
        """
        Al detener el timer:
        - Buscamos la ÚLTIMA línea de timesheet del usuario en esa tarea.
        - La marcamos como registro de llegada para ESA sesión.
        """
        res = super().action_timer_stop()

        Analytic = self.env['account.analytic.line']

        for task in self:
            # Si por alguna razón nunca se calculó una llegada en esta sesión,
            # no hacemos nada.
            if not task.fs_arrival_datetime:
                continue

            # Última línea de tiempos del usuario actual en esta tarea
            last_line = Analytic.search([
                ('task_id', '=', task.id),
                ('employee_id.user_id', '=', self.env.user.id),
            ], order='create_date desc, id desc', limit=1)

            if last_line:
                last_line.write({
                    # esta línea representa la llegada de ESTA sesión
                    'fs_is_arrival': True,
                    # si añadiste estos campos en account.analytic.line
                    'fs_arrival_datetime': task.fs_arrival_datetime,
                    'fs_arrival_status': task.fs_arrival_status or False,
                    'fs_delay_minutes': task.fs_delay_minutes or 0,
                })

        return res

    @api.model
    def _cron_mark_fs_no_show_tasks(self):
        """Marcar como 'no_show' las tareas vencidas sin NINGUNA llegada registrada."""
        now = fields.Datetime.now()

        domain = [
            ('date_deadline', '!=', False),
            ('date_deadline', '<', now),
            ('fs_arrival_status', '=', False),
            ('is_closed', '=', False),  # etapa no cerrada
        ]
        tasks = self.search(domain)
        for task in tasks:
            delay_minutes = int(round(
                (now - task.date_deadline).total_seconds() / 60.0
            ))
            task.write({
                'fs_arrival_status': 'no_show',
                'fs_delay_minutes': max(delay_minutes, 0),
            })
