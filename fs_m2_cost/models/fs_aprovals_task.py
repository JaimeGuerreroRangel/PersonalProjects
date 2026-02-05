from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    # --- Relación con aprobaciones (reprogram + viáticos + lo que venga) ---
    approval_request_ids = fields.One2many(
        "approval.request",
        "fs_task_id",
        string="Aprobaciones",
    )
    approval_count = fields.Integer(
        string="# Aprobaciones",
        compute="_compute_approval_count",
    )

    # --- Relación con gastos ---
    expense_ids = fields.One2many(
        "hr.expense",
        "task_id",
        string="Gastos",
    )
    expense_count = fields.Integer(
        string="# Gastos",
        compute="_compute_expense_count",
    )

    # ---------------------------
    #   COMPUTES
    # ---------------------------

    def _compute_approval_count(self):
        for task in self:
            task.approval_count = len(task.approval_request_ids)

    def _compute_expense_count(self):
        for task in self:
            task.expense_count = len(task.expense_ids)

    # ---------------------------
    #   ACCIONES: APROVALS
    # ---------------------------

    def action_view_approvals(self):
        """Smart button: ver todas las aprobaciones ligadas a la tarea."""
        self.ensure_one()
        action = self.env.ref("approvals.approval_request_action").read()[0]
        action.update(
            {
                "domain": [("fs_task_id", "=", self.id)],
                "context": {
                    "default_task_id": self.id,
                },
            }
        )
        return action
        
    # Flujo de aprobación:
    # Cuando se crea una solicitud de viáticos o reprogramación
    # El sistema une todos los coordinadores de los 3 tipos usando |
    # Crea un aprobador para cada uno en el loop for
    # Los usuarios reciben la solicitud de aprobación

    def action_request_travel(self):
        """Botón: Solicitud de viáticos (solo con tarea aceptada)."""
        self.ensure_one()

        if self.fs_status != "accepted":
            raise UserError(
                _("Solo puedes solicitar viáticos cuando la tarea está ACEPTADA.")
            )

        company = self.company_id or self.env.company

        # Categoría configurada por empresa (Ajustes -> Field Service)
        category = company.fs_travel_approval_category_id
        if not category:
            raise UserError(
                _(
                    "No está configurada la categoría de aprobación para viáticos en la compañía '%s'.\n"
                    "Ve a Ajustes → Field Service y configura 'Categoría aprobación viáticos (FS)'."
                )
                % company.display_name
            )

        # Validación defensiva: asegurar que pertenezca a la misma compañía
        if getattr(category, "company_id", False) and category.company_id != company:
            raise UserError(
                _(
                    "La categoría de viáticos configurada no pertenece a la misma compañía de la tarea.\n"
                    "Compañía de la tarea: %s\n"
                    "Compañía de la categoría: %s"
                )
                % (company.display_name, category.company_id.display_name)
            )

        # "Gerentes" (coordinadores) Cambiar | por or si da error
        managers = (
            company.fs_coordinator_installation_ids
            | company.fs_coordinator_leveling_ids
            | company.fs_coordinator_evaluator_ids
        )
        if not managers:
            raise UserError(
                _(
                    "No hay ningún coordinador configurado para aprobaciones de viáticos."
                )
            )

        # Validación defensiva: approver espera res.users
        # if manager._name != "res.users":
        #     raise UserError(
        #         _("El coordinador configurado no es un usuario (res.users).")
        #     )

        name = _("Viáticos tarea %s") % (self.fs_sequence or self.name)

        approval_vals = {
            "name": name,
            "request_owner_id": self.env.user.id,
            "category_id": category.id,
            "fs_task_id": self.id,
            "reason": _("Solicitud de viáticos para la tarea %s")
            % (self.display_name,),
        }

        # Set company_id solo si el modelo lo tiene (evita crash por versiones/capas)
        if "company_id" in self.env["approval.request"]._fields:
            approval_vals["company_id"] = company.id

        approval = self.env["approval.request"].create(approval_vals)

        for manager in managers:
            self.env["approval.approver"].create(
                {
                    "request_id": approval.id,
                    "user_id": manager.id,
                }
            )

        link = "%s/web#id=%s&model=approval.request&view_type=form" % (
            self.get_base_url(),
            approval.id,
        )
        body = (
            _(
                "Se ha creado una <b>solicitud de viáticos</b> para esta tarea.<br/>"
                'Solicitud: <a href="%s">Abrir aprobación</a>'
            )
            % link
        )
        self.message_post(body=body, subtype_xmlid="mail.mt_note")

        return {
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "view_mode": "form",
            "res_id": approval.id,
            "target": "current",
        }

    # ---------------------------
    #   ACCIONES: GASTOS
    # ---------------------------

    def action_view_expenses(self):
        """Smart button / Declarar gastos: ver gastos de la tarea."""
        self.ensure_one()
        action = self.env.ref("hr_expense.hr_expense_actions_all").read()[0]
        action.update(
            {
                "domain": [("task_id", "=", self.id)],
                "context": {
                    "default_task_id": self.id,
                },
            }
        )
        return action

    def action_declare_expenses(self):
        """Botón 'Declarar gastos' → reutilizamos la acción de ver gastos."""
        self.ensure_one()
        return self.action_view_expenses()

    # notify coordinator when measurement is done

    def _fs_notify_mesurement_confirmed(self):
        """Notifica al coordinador de colocación cuando la toma de medidas está finalizada."""
        self.ensure_one()

        company = self.company_id or self.env.company
        coordinator = company.fs_coordinator_installation_id
        if not coordinator:
            # Si no hay coordinador configurado, no hacemos nada (o log opcional)
            return

        # Plantilla de correo
        template = self.env.ref(
            "fs_m2_cost.mail_fs_measurement_confirmed",
            raise_if_not_found=False,
        )

        if template:
            template.send_mail(
                self.id,
                email_values={
                    "email_to": coordinator.email,
                },
                force_send=True,
            )

        # Crear actividad en el chatter
        MailActivity = self.env["mail.activity"]
        todo_type = self.env.ref("mail.mail_activity_data_todo")
        model_task = self.env["ir.model"]._get_id("project.task")

        MailActivity.create(
            {
                "activity_type_id": todo_type.id,
                "res_model_id": model_task,
                "res_id": self.id,
                "user_id": coordinator.id,
                "summary": _("Toma de medidas confirmada"),
                "note": _(
                    "La tarea %(task)s ya tiene la toma de medidas confirmada y está lista para programar la colocación.",
                    task=self.display_name,
                ),
            }
        )

    def _fs_notify_coordinator_on_create(self):
        """Envia correo y crea actividad al coordinador según el tipo de servicio."""
        MailActivity = self.env["mail.activity"]
        IrModel = self.env["ir.model"]
        model_id = IrModel._get_id("project.task")
        todo_type = self.env.ref("mail.mail_activity_data_todo")

        for task in self:
            line = task.fs_related_sale_line_id
            if not line or not line.product_id:
                continue

            tmpl = line.product_id.product_tmpl_id
            company = task.company_id or self.env.company

            coordinator = False
            template_xmlid = False
            summary = False

            if tmpl.fs_is_installation:
                coordinator = company.fs_coordinator_installation_id
                template_xmlid = "fs_m2_cost.mail_fs_task_created_installation"
                summary = _("Nueva tarea de colocación generada")
            elif tmpl.fs_is_leveling:
                coordinator = company.fs_coordinator_leveling_id
                template_xmlid = "fs_m2_cost.mail_fs_task_created_leveling"
                summary = _("Nueva tarea de nivelación generada")
            elif tmpl.fs_is_evaluation:
                coordinator = company.fs_coordinator_evaluator_id
                template_xmlid = "fs_m2_cost.mail_fs_task_created_evaluation"
                summary = _("Nueva tarea de evaluación generada")

            if not coordinator or not template_xmlid:
                continue

            # --- Enviar correo (plantilla) ---
            email_tmpl = self.env.ref(template_xmlid, raise_if_not_found=False)
            if email_tmpl and coordinator.partner_id.email:
                email_tmpl.send_mail(
                    task.id,
                    email_values={
                        "email_to": coordinator.partner_id.email,
                    },
                    force_send=True,
                )

            # --- Crear actividad en el chatter ---
            MailActivity.create(
                {
                    "activity_type_id": todo_type.id,
                    "res_model_id": model_id,
                    "res_id": task.id,
                    "user_id": coordinator.id,
                    "summary": summary,
                    "note": _(
                        "Se ha creado la tarea %(task)s para el cliente %(partner)s.",
                        task=task.display_name,
                        partner=(
                            task.sale_order_id.partner_id.display_name
                            if task.sale_order_id and task.sale_order_id.partner_id
                            else ""
                        ),
                    ),
                }
            )
