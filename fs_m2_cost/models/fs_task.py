from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class ProjectTask(models.Model):
    _inherit = "project.task"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        help="Orden de venta origen de la tarea.",
    )

    fs_delivery_status = fields.Selection(
        related="sale_order_id.delivery_status",
        string="Estado de entrega",
        store=True,
        readonly=True,
    )

    fs_effective_date = fields.Datetime(
            related="sale_order_id.effective_date",
            string="Fecha efectiva de entrega",
            store=True,
            readonly=True,
        ) 

    # 🔹 Tipo de servicio en la tarea (relacionado al servicio)
    fs_service_type_id = fields.Many2one(
        "field.service.type",
        string="Tipo de servicio FS",
        help="Tipo de servicio de Field Service para esta tarea.",
        compute="_compute_fs_service_type",
        store=True,
    )

    # 🔹 Secuencia por tipo de servicio
    fs_sequence = fields.Char(
        string="Secuencia Field Service",
        readonly=True,
        copy=False,
        help="Folio de la tarea según el tipo de servicio.",
    )

    # 🔹 Línea de venta del servicio (la ligas tú manualmente, o la llenamos desde sale_line_id)
    fs_related_sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Servicio relacionado",
        help="Línea de venta (servicio) que originó esta tarea.",
    )

    fs_service_location_id = fields.Many2one(
        "res.partner",
        string="Ubicación del servicio",
        related="sale_order_id.partner_shipping_id",
        store=True,
        readonly=True,
    )

    fs_service_installation_id = fields.Many2one(
        "res.partner",
        string="Ubicación de la instalación",
        related="sale_order_id.fs_direccion_instalacion",
        store=True,
        readonly=True,
    )

    fs_link_google_maps = fields.Char(
        string="Enlace de Google Maps",
        related="sale_order_id.fs_link_google_maps",
        store=True,
        readonly=True,
    )

    
    fs_service_specialty_id = fields.Many2one(
        "field.service.specialty",
        string="Especialidad del servicio",
        store=True,
    )

    fs_expected_m2 = fields.Float(
        string="M2 planeados",
        help="M2 totales a instalar, tomados del material relacionado en la OV.",
        readonly=False,
    )

    task_kpi_ids = fields.One2many(
        "task.kpi",
        "task_id",
        string="Historial de cambios",
    )


    fs_status = fields.Selection(
        [
            ("to_assign", "Por asignar"),
            ("rejected", "Rechazada"),
            ("reschedule", "En reprogramación"),
            ("accepted", "Aceptada"),
        ],
        string="Estado Field Service",
        default="to_assign",
        tracking=True,
    )

    fs_decision_locked = fields.Boolean(
        string="Decisión bloqueada",
        help="Si está activo, el operador ya respondió (Aceptar/Rechazar/Reprogramar) "
             "y no puede volver a hacerlo hasta que el coordinador modifique tarea/fechas.",
        default=False,
    )


    approval_request_ids = fields.One2many(
        "approval.request",
        "fs_task_id",
        string="Aprobaciones",
    )

    approval_request_count = fields.Integer(
        string="Núm. aprobaciones",
        compute="_compute_approval_request_count",
    )

    fs_fecha_estimada_instalacion = fields.Datetime(
        string="Fecha estimada del servicio",
        related="sale_order_id.fs_fecha_estimada_instalacion",
        store=True,
        readonly=True,
    )

    fs_commission_paid = fields.Boolean(
        string="Comisión pagada",
        compute="_compute_fs_commission_info",
    )
    fs_commission_bill_count = fields.Integer(
        string="Facturas de comisión",
        compute="_compute_fs_commission_info",
    )

    def _compute_fs_commission_info(self):
        AAL = self.env["account.analytic.line"]
        for task in self:
            lines = AAL.search([
                ("task_id", "=", task.id),
                ("fs_m2_cost", ">", 0),
            ])

            if not lines:
                task.fs_commission_paid = False
                task.fs_commission_bill_count = 0
                continue

            # Facturas válidas (no canceladas)
            bills = lines.mapped("fs_commission_move_id").filtered(lambda m: m and m.state != "cancel")
            task.fs_commission_bill_count = len(set(bills.ids))

            # Pagada = todas las líneas comisionables tienen factura válida
            task.fs_commission_paid = bool(lines) and all(lines.mapped("fs_commission_paid"))
    
    def action_view_fs_commission_bills(self):
        self.ensure_one()
        AAL = self.env["account.analytic.line"]

        lines = AAL.search([
            ("task_id", "=", self.id),
            ("fs_m2_cost", ">", 0),
            ("fs_commission_move_id", "!=", False),
        ])

        bills = lines.mapped("fs_commission_move_id").filtered(lambda m: m.state != "cancel")
        bills = bills.browse(list(set(bills.ids)))

        if not bills:
            raise UserError(_("Esta tarea no tiene facturas de comisión relacionadas."))

        action = self.env.ref("account.action_move_in_invoice_type").read()[0]
        action["domain"] = [("id", "in", bills.ids)]
        action["context"] = {"create": False}
        return action


    
    # ==========================
    # Contador de aprobaciones
    # ==========================



    @api.depends("approval_request_ids")
    def _compute_approval_request_count(self):
        for task in self:
            task.approval_request_count = len(task.approval_request_ids)

    def action_view_approval_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("approvals.approval_request_action")
        action["domain"] = [("fs_task_id", "=", self.id)]
        action["context"] = {
            "default_task_id": self.id,
            "search_default_my_approvals": 0,
        }
        return action




    
    # ==========================
    # CÓMPUTOS Y HELPERS
    # ==========================

    
    #control de la aceptacion,rechazo y reprogramacion de citas
    def action_fs_accept(self):
        self.ensure_one()

        if self.fs_decision_locked:
            raise UserError(_("Ya se ha tomado una decisión para esta tarea."))

        # Estado
        self.fs_status = "accepted"
        self.fs_decision_locked = True

        # KPI
        self._create_task_kpi_entry(new_status="accepted")

        # Mensaje en chatter
        msg = _(
            "La tarea ha sido ACEPTADA por %s."
        ) % (self.env.user.display_name,)
        self.message_post(body=msg, subtype_xmlid="mail.mt_note")

         # 🔹 Si es tarea de evaluación (toma de medidas), notificar al coordinador de colocación
        self._fs_notify_coordinator_on_create()

        return True


    def action_fs_reject(self):
        self.ensure_one()
        if self.fs_decision_locked:
            raise UserError(_("Ya se ha tomado una decisión para esta tarea."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Motivo de rechazo"),
            "res_model": "task.kpi.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_id": self.id,
                "default_action_type": "reject",
            },
        }


    def action_fs_reprogram(self):
        """Abrir wizard para reprogramar."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "task.kpi.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_id": self.id,
                "default_action_type": "reschedule",
            },
        }

    # computo del tipo de servicio
    @api.depends("fs_related_sale_line_id", "fs_related_sale_line_id.product_id")
    def _compute_fs_service_type(self):
        """Tipo de servicio según el producto del servicio relacionado."""
        for task in self:
            service_line = task.fs_related_sale_line_id
            if service_line and service_line.product_id:
                task.fs_service_type_id = service_line.product_id.product_tmpl_id.fs_service_type_id
            else:
                task.fs_service_type_id = False



    # contaador de cambios de estatus en la tarea
    def _fs_get_kpi_prev_status_and_next_count(self):
        """Regresa (estatus_anterior, siguiente_contador) por tarea."""
        result = {}
        TaskKpi = self.env["task.kpi"]
        for task in self:
            kpIs = TaskKpi.search([("task_id", "=", task.id)], order="change_date, id")
            if kpIs:
                last = kpIs[-1]
                prev_status = last.current_status or "Por confirmar"
                next_count = (last.change_count or 0) + 1
            else:
                prev_status = "Por confirmar"
                next_count = 1
            result[task.id] = (prev_status, next_count)
        return result

    # Llena campos derivados desde fs_related_sale_line_id
    def _fs_fill_from_sale_line(self):
        """
        Rellena campos derivados a partir de fs_related_sale_line_id:
        - fs_service_specialty_id
        - fs_expected_m2
        - sale_order_id (por si no viene)
        """
        for task in self:
            line = task.fs_related_sale_line_id
            if not line:
                continue

            # 3) Especialidad desde el producto
            #    (según lo que pediste: product_id.fs_service_specialty_id)
            specialty = getattr(line.product_id, "fs_specialty_id", False)
            if specialty:
                task.fs_service_specialty_id = specialty

            # 4) M2 esperados = cantidad de la línea de venta
            task.fs_expected_m2 = line.product_uom_qty or 0.0

            # Aseguramos también la OV, por si algo viene vacío
            if not task.sale_order_id and line.order_id:
                task.sale_order_id = line.order_id

    def _fs_assign_sequence(self):
        """
        Asigna la secuencia fs_sequence según el tipo de servicio (fs_service_type_id)
        y su sequence_id configurada.
        """
        for task in self:
            if task.fs_sequence:
                continue  # ya tiene folio

            service_type = task.fs_service_type_id
            if service_type and service_type.sequence_id:
                task.fs_sequence = service_type.sequence_id.next_by_id()

    def _fs_recompute_sale_line_cost(self):
        """
        (cantidad_a_instalar / tab_m2) * tarifa_x

        - cantidad_a_instalar: suma de m2 del material relacionado en la OV.
        - tab_m2, tarifa_x: del tabulador y del usuario asignado.
        Además:
        - allocated_hours = (fs_expected_m2 / tab_m2) * tiempo_tabulado
        """
        FieldServiceRate = self.env["field.service.rate"]

        for task in self:
            service_line = task.fs_related_sale_line_id
            if not service_line or not service_line.product_id:
                continue

            service_tmpl = service_line.product_id.product_tmpl_id

            # Material relacionado
            material_tmpl = service_tmpl.fs_material_template_id
            if not material_tmpl:
                continue

            # OV
            sale_order = task.sale_order_id or service_line.order_id
            if not sale_order:
                continue

            # Cantidad total a instalar = suma de m2 del material en la OV
            total_m2_install = 0.0
            for line in sale_order.order_line:
                if (
                    line.product_template_id == material_tmpl
                    and not line.display_type
                    and line.product_uom_qty
                ):
                    total_m2_install += line.product_uom_qty

            if not total_m2_install:
                continue

            # Tabulador
            tab = FieldServiceRate.search(
                [("service_id", "=", service_tmpl.id)],
                limit=1,
            )
            if not tab or not tab.tab_m2:
                continue

            # ================================
            # ⏱ Cálculo de horas asignadas
            # ================================
            # fs_expected_m2 = total de m2 a instalar
            task.fs_expected_m2 = total_m2_install

            if tab.tiempo_tabulado:
                task.allocated_hours = (task.fs_expected_m2 / tab.tab_m2) * tab.tiempo_tabulado
            else:
                # Si no hay tiempo tabulado definido, dejamos 0
                task.allocated_hours = 0.0

            # ================================
            # 💰 Cálculo de costo (como antes)
            # ================================
            # Técnico asignado (en tu modelo solo existe user_ids)
            technician = task.user_ids[:1] and task.user_ids[:1][0] or False
            if not technician:
                # No hay asignado → no calculamos costo, pero sí dejamos fs_expected_m2/allocated_hours
                continue

            tariff_type = getattr(technician, "tariff_type", "a") or "a"
            tarifa = tab.tarifa_a if tariff_type == "a" else tab.tarifa_b

            # Costo total del servicio
            cost_total = (total_m2_install / tab.tab_m2) * tarifa

            # Costo unitario (por “hora” del servicio en la línea)
            service_line.price_unit = cost_total # Cambio por error que comento wess 09/feb antes es purchase_price

    # ==========================
    # OVERRIDES: write y create
    # ==========================

    # Crear entrada en task.kpi al cambiar estatus FS
    def _create_task_kpi_entry(self, new_status, reason=False, new_date=False):
        """Crea registro de task.kpi y actualiza contador, estados, etc."""
        TaskKpi = self.env["task.kpi"]
        status_dict = dict(self._fields["fs_status"].selection)

        for task in self:
            last_kpi = TaskKpi.search(
                [("task_id", "=", task.id)],
                order="change_date desc, id desc",
                limit=1,
            )

            if last_kpi:
                previous_status = last_kpi.current_status or "Por asignar"
                change_count = (last_kpi.change_count or 0) + 1
            else:
                previous_status = "Por asignar"
                change_count = 1

            vals = {
                "task_id": task.id,
                "change_date": fields.Datetime.now(),
                "user_id": self.env.user.id,
                "previous_status": previous_status,
                "current_status": status_dict.get(new_status, new_status),
                "reason": reason or "",
                "change_count": change_count,
            }
            if new_date:
                vals["reschedule_date"] = new_date

            TaskKpi.create(vals)

    def write(self, vals):
        TaskKpi = self.env["task.kpi"]
        planning_tasks = self.env["project.task"]
        measurement_done_tasks = self.env["project.task"]

        new_stage_id = vals.get("stage_id")
        new_stage = False

        # 1) Antes de super(): detectar qué tareas cambian de etapa
        if new_stage_id:
            new_stage = self.env["project.task.type"].browse(new_stage_id)
            for task in self:
                if task.stage_id.id != new_stage_id:
                    # Etapa de planificación
                    if new_stage.fs_is_planning_stage:
                        planning_tasks |= task
                    # Etapa de "medidas finalizadas"
                    if new_stage.fs_is_done_stage:
                        measurement_done_tasks |= task

        user = self.env.user

        # ¿Es operador FSM (grupo user)?
        is_fsm_user = user.has_group("industry_fsm.group_fsm_user")
        # ¿Es manager FSM?
        is_fsm_manager = user.has_group("industry_fsm.group_fsm_manager")

        # Solo bloqueamos si:
        #   - pertenece al grupo de usuario FSM
        #   - y NO pertenece al grupo manager FSM
        if is_fsm_user and not is_fsm_manager:
            campos_bloqueados = {
                "name",
                "project_id",
                "user_ids",
                "date_deadline",
                "allocated_hours",
                "tag_ids",
                "sale_line_id",
                "under_warranty", 
                "partner_id",
                "partner_phone", 
                "parent_id",
                "secuence",
                "email_cc", 
                
            }

            campos_intentados = campos_bloqueados.intersection(vals.keys())
            if campos_intentados:
                # Construimos etiquetas "Nombre campo (nombre_tecnico)"
                etiquetas = []
                for campo in campos_intentados:
                    field = self._fields.get(campo)
                    if field:
                        # field.string = etiqueta que ves en la vista
                        etiqueta = "%s (%s)" % (field.string or campo, campo)
                    else:
                        etiqueta = campo
                    etiquetas.append(etiqueta)

                etiquetas = sorted(etiquetas)

                raise UserError(_(
                    "No tienes permisos para modificar los siguientes campos de la tarea:\n- %s"
                ) % "\n- ".join(etiquetas))
        # Si pasa las validaciones, seguimos con el comportamiento normal

        # 2) Escritura normal
        res = super().write(vals)

        # 3) Si un coordinador cambia asignados o fecha, desbloqueamos decisión
        fields_trigger_unlock = {
            "user_ids",
            "date_deadline",
            "fs_service_location_id",
            "fs_service_installation_id",
        }
        if fields_trigger_unlock & set(vals.keys()):
            if self.env.user.has_group("industry_fsm.group_fsm_manager"):
                for task in self:
                    task.fs_decision_locked = False
                    task.fs_status = "to_assign"

        # 4) Crear KPI inicial si la nueva etapa es de planificación
        if new_stage_id and new_stage and new_stage.fs_is_planning_stage:
            for task in planning_tasks:
                if TaskKpi.search_count([("task_id", "=", task.id)]) == 0:
                    TaskKpi.create({
                        "task_id": task.id,
                        "change_date": fields.Datetime.now(),
                        "user_id": self.env.user.id,
                        "previous_status": "Por confirmar",
                        "current_status": "Planificado",
                        "change_count": 1,
                    })

        # 5) Notificación de toma de medidas confirmada cuando entra a etapa final
        if measurement_done_tasks:
            measurement_done_tasks._fs_notify_mesurement_confirmed()

        # 6) Si cambian los asignados, recalculamos costo
        if "user_ids" in vals or "user_id" in vals:
            self._fs_recompute_sale_line_cost()

        # 7) Si cambiamos la línea relacionada, rellenamos campos derivados y secuencia
        if "fs_related_sale_line_id" in vals:
            self._fs_fill_from_sale_line()
            self._compute_fs_service_type()
            self._fs_assign_sequence()

        return res



    @api.model_create_multi
    def create(self, vals_list):
        # Crear las tareas normalmente
        tasks = super().create(vals_list)

        # 2) Intentar rellenar fs_related_sale_line_id desde sale_line_id de los vals
        for task, vals in zip(tasks, vals_list):
            # Si ya viene fs_related_sale_line_id, lo respetamos
            if not task.fs_related_sale_line_id:
                sale_line_id = vals.get("sale_line_id")
                if sale_line_id:
                    task.fs_related_sale_line_id = self.env["sale.order.line"].browse(sale_line_id)
                else:
                    # Fallback: si el modelo realmente tiene sale_line_id como campo (FSM / sale_project),
                    # lo usamos aunque no venga en vals explícitamente.
                    sale_line = getattr(task, "sale_line_id", False)
                    if sale_line:
                        task.fs_related_sale_line_id = sale_line

        # 3) Rellenar especialidad, m2 esperados y OV desde la línea de venta
        tasks._fs_fill_from_sale_line()

        # 4) Recalcular tipo de servicio (para la secuencia)
        tasks._compute_fs_service_type()

        # 5) Asignar secuencia por tipo de servicio (ya con fs_service_type_id lleno)
        tasks._fs_assign_sequence()

        # 6) Notificar toma de medidas confirmada si aplica
        tasks._fs_notify_coordinator_on_create()

        # 7) Recalcular costo para TODAS las tareas creadas
        tasks._fs_recompute_sale_line_cost()

        return tasks
