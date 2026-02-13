from odoo import api, fields, models, _
from odoo.exceptions import UserError
import io
import base64


class FSTimesheetReportWizard(models.TransientModel):
    _name = "fs.timesheet.report.wizard"
    _description = "Informe reembolso socio (Field Service)"
    
    name = fields.Char(string="Informe de Reembolso", default="Informe de Reembolso", readonly=True)

    # --- Filtros ---
    user_ids = fields.Many2many(
        "res.users",
        "fs_timesheet_report_wizard_user_rel",
        "wizard_id",
        "user_id",
        string="Colaboradores",
        help="Colaboradores a analizar. Si se deja vacío, se mostrarán todos.",
    )
    date_from = fields.Date(string="Desde fecha")
    date_to = fields.Date(string="Hasta fecha")
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        help="Filtrar por una orden de venta específica.",
    )

    # --- Datos de cabecera tipo reporte papel ---
    report_date = fields.Datetime(
        string="Fecha del reporte",
        default=fields.Datetime.now,
        readonly=True,
    )
    collaborator_ref = fields.Char(
        string="ID de socio",
        compute="_compute_collaborator_header",
        readonly=True,
    )
    collaborator_name = fields.Char(
        string="Nombre del colaborador",
        compute="_compute_collaborator_header",
        readonly=True,
    )
    reimbursement_method = fields.Char(
        string="Método de reembolso",
        default="Comprobante",
        readonly=True,
    )
    provider_name = fields.Char(
        string="Proveedor",
        default="N/A",
        readonly=True,
    )

    # --- Resultados ---
    line_ids = fields.One2many(
        "fs.timesheet.report.line", "wizard_id", string="Líneas de horas"
    )
    total_amount = fields.Float(
        string="Total general",
        compute="_compute_totals",
        readonly=True,
    )

    # --- Exportación de archivos ---
    export_file = fields.Binary(
        string="Archivo generado",
        readonly=True,
    )
    export_filename = fields.Char(
        string="Nombre del archivo",
        readonly=True,
    )

    @api.depends("user_ids")
    def _compute_collaborator_header(self):
        """
        Si hay un solo colaborador seleccionado, mostramos su ref y nombre.
        Si hay varios, indicamos 'Varios'.
        Si no hay ninguno, dejamos vacío.
        """
        for wiz in self:
            if len(wiz.user_ids) == 1:
                user = wiz.user_ids[0]
                wiz.collaborator_ref = user.ref or ""
                wiz.collaborator_name = user.name or ""
            elif len(wiz.user_ids) > 1:
                wiz.collaborator_ref = ""
                wiz.collaborator_name = "Varios colaboradores"
            else:
                wiz.collaborator_ref = ""
                wiz.collaborator_name = ""

    @api.depends("line_ids.fs_m2_cost")
    def _compute_totals(self):
        for wiz in self:
            wiz.total_amount = sum(wiz.line_ids.mapped("fs_m2_cost"))

    def action_compute(self):
        """Buscar timesheets según filtros y llenar las líneas del wizard."""
        self.ensure_one()
        AAL = self.env["account.analytic.line"]

        # Armar dominio
        domain = [("fs_m2_cost", ">", 0)]  # Solo las que tienen costo FS
        if self.user_ids:
            domain.append(("user_id", "in", self.user_ids.ids))
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        if self.sale_order_id:
            # Ligamos por la tarea: task_id.sale_order_id
            domain.append(("task_id.sale_order_id", "=", self.sale_order_id.id))

        timesheets = AAL.search(domain, order="date, id")

        # Limpiar líneas previas del wizard
        self.line_ids.unlink()

        line_vals = []
        for ts in timesheets:
            task = ts.task_id
            has_report = False
            is_signed = False

            # producto del servicio relacionado a la tarea
            related_product_code = ""
            if (
                task
                and task.fs_related_sale_line_id
                and task.fs_related_sale_line_id.product_id
            ):
                related_product_code = (
                    task.fs_related_sale_line_id.product_id.name or ""
                )
            else:
                # fallback: producto del timesheet si no hay relación
                related_product_code = ts.product_id.name or ""

            if task:
                # Verificar reporte
                attachments = self.env['ir.attachment'].search([
                    ('res_model', '=', 'project.task'),
                    ('res_id', '=', task.id),
                    ('name', 'ilike', 'reporte'),
                ], limit=1)
                has_report = bool(attachments)
                
                # Verificar firma
                is_signed = bool(task.worksheet_signature)
            
            # Estado de pago desde el timesheet
            is_paid = bool(ts.fs_commission_paid)
            bill = ts.fs_commission_move_id

            line_vals.append(
                {
                    "wizard_id": self.id,
                    "timesheet_id": ts.id,
                    "date": ts.date,
                    "task_id": task.id if task else False,
                    "task_stage_name": task.stage_id.name if task and task.stage_id else "",
                    "fs_sequence": task.fs_sequence if task else "",
                    "user_id": ts.user_id.id,
                    "product_id": ts.product_id.id if ts.product_id else False,
                    "sale_line_id": (
                        task.fs_related_sale_line_id.id
                        if task and task.fs_related_sale_line_id
                        else False
                    ),
                    "sale_order_id": (
                        task.sale_order_id.name if task and task.sale_order_id else ""
                    ),
                    "product_code": related_product_code,  # AHORA VIENE DEL SERVICIO RELACIONADO
                    "fs_m2_cost": ts.fs_m2_cost or 0.0,
                    "qty_m2": ts.fs_m2_real,  # Cantidad de m²
                    "unit_rate": (ts.fs_m2_cost / ts.fs_m2_real)
                    or 0.0,  # Tarifa unitaria - ajusta si ya la tienes
                    "is_paid": is_paid,
                    "vendor_bill_id": bill.id if bill else False,
                    "has_report": has_report,
                }
            )

        if line_vals:
            self.env["fs.timesheet.report.line"].create(line_vals)

        return {
            "type": "ir.actions.act_window",
            "res_model": "fs.timesheet.report.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("fs_m2_cost.fs_timesheet_report_wizard_view").id,
            "res_id": self.id,
            "target": "current",
        }

    # ==========================
    # Metodo para generar pagos
    # ==========================
    def action_generate_payments(self):
        """
        Genera una factura de proveedor por cada usuario encontrado en line_ids,
        SOLO considerando líneas que aún no estén pagadas (is_paid = False).

        - Diario: configurado en Ajustes (fs_commission_journal_id)
        - Producto: configurado en Ajustes (fs_commission_product_id)
        - Importe: suma de fs_m2_cost por usuario (solo líneas no pagadas).
        """
        self.ensure_one()

        # Nota: en multi-company, env.company puede no ser la misma compañía del diario.
        # Tomamos primero la compañía "base" del wizard/entorno y luego ajustamos.
        company = self.env.company
        journal = company.fs_commission_journal_id
        product = company.fs_commission_product_id

        if not journal or not product:
            raise UserError(
                _(
                    "Configura primero el diario y el producto de comisión en Ajustes generales:\n"
                    "- Diario de comisiones FS\n"
                    "- Producto comisión FS"
                )
            )

        # Compañía real de la operación: prioriza la del diario
        company = journal.company_id or company
        if not company:
            raise UserError(
                _("No se pudo determinar la compañía para generar las facturas.")
            )

        # Blindaje de contexto multi-company (evita company_id vacío en account.move.create)
        Move = (
            self.env["account.move"]
            .with_company(company)
            .with_context(
                allowed_company_ids=company.ids,
                default_company_id=company.id,
            )
        )

        # Solo consideramos líneas NO pagadas
        lines_to_pay = self.line_ids.filtered(lambda l: not l.is_paid)

        if not lines_to_pay:
            raise UserError(
                _("Todas las líneas ya están pagadas. No hay nada por generar.")
            )

        # Agrupar montos y líneas por usuario
        amounts_per_user = {}
        lines_per_user = {}
        for line in lines_to_pay:
            if not line.user_id:
                continue
            amounts_per_user.setdefault(line.user_id, 0.0)
            amounts_per_user[line.user_id] += line.fs_m2_cost or 0.0

            lines_per_user.setdefault(
                line.user_id, self.env["fs.timesheet.report.line"]
            )
            lines_per_user[line.user_id] |= line

        if not amounts_per_user:
            raise UserError(
                _("No hay líneas con usuario para generar facturas de proveedor.")
            )

        created_moves = self.env["account.move"]

        for user, amount in amounts_per_user.items():
            if not amount:
                continue

            partner = user.partner_id
            if not partner:
                raise UserError(
                    _(
                        "El usuario %s no tiene un contacto asociado (partner_id). "
                        "Asigna un contacto al usuario antes de generar los pagos."
                    )
                    % user.name
                )

            # Cuenta contable de gasto desde el producto o su categoría
            expense_account = (
                product.property_account_expense_id
                or product.categ_id.property_account_expense_categ_id
            )
            if not expense_account:
                raise UserError(
                    _(
                        "El producto de comisión '%s' no tiene configurada una cuenta de gasto.\n"
                        "Configúrala en el producto o en su categoría."
                    )
                    % product.display_name
                )

            if (
                hasattr(expense_account, "company_id")
                and expense_account.company_id
                and expense_account.company_id != company
            ):
                raise UserError(
                    _(
                        "La cuenta de gasto '%s' asignada al producto de comisión pertenece a otra compañía.\n"
                        "Asegúrate de que la cuenta contable, el diario y el producto pertenezcan a la misma compañía."
                    )
                    % (
                        expense_account.display_name,
                        expense_account.company_id.display_name,
                        company.display_name,
                    )
                )

            move_vals = {
                "move_type": "in_invoice",
                "company_id": company.id,  # <- FIX CLAVE (evita res.company() vacío)
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.context_today(self),
                # (Opcional) si quieres forzar también la fecha contable:
                # "date": fields.Date.context_today(self),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": _("Comisión Field Service - %s") % (user.name,),
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": expense_account.id,
                        },
                    )
                ],
            }

            move = Move.create(move_vals)
            created_moves |= move

            # Marcar timesheets como pagados para este usuario
            related_lines = lines_per_user.get(
                user, self.env["fs.timesheet.report.line"]
            )
            aal_to_mark = related_lines.mapped("timesheet_id")
            aal_to_mark.write(
                {
                    "fs_commission_move_id": move.id,
                    "fs_commission_paid": True,
                }
            )

            # Marcar también las líneas del wizard (para que el usuario lo vea en esta ejecución)
            related_lines.write(
                {
                    "is_paid": True,
                    "vendor_bill_id": move.id,
                }
            )

        # Abrir las facturas generadas
        action = self.env.ref("account.action_move_in_invoice_type").read()[0]
        action["domain"] = [("id", "in", created_moves.ids)]
        return action

    # ==========================
    #  Exportar a Excel
    # ==========================
    def action_export_excel(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("No hay líneas para exportar.")

        try:
            import xlsxwriter
        except ImportError:
            raise UserError("Falta el paquete python 'xlsxwriter' en el servidor.")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Reembolso socio")

        # ===== FORMATO =====
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#0070C0",  # azul
                "font_color": "white",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
            }
        )
        text_format = workbook.add_format(
            {
                "border": 1,
            }
        )
        amount_format = workbook.add_format(
            {
                "border": 1,
                "num_format": "#,##0.00",
            }
        )
        total_label_format = workbook.add_format(
            {
                "bold": True,
                "border": 1,
            }
        )
        total_amount_format = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "num_format": "#,##0.00",
            }
        )

        # Anchos de columna
        sheet.set_column("A:A", 12)  # Fecha
        sheet.set_column("B:B", 15)  # Tarea
        sheet.set_column("C:C", 35)  # Colaborador
        sheet.set_column("D:D", 20)  # Orden de venta
        sheet.set_column("E:E", 60)  # Servicio
        sheet.set_column("F:F", 15)  # Cantidad m2
        sheet.set_column("G:G", 15)  # M2
        sheet.set_column("H:H", 15)  # Precio unitario
        sheet.set_column("I:I", 15)  # M2 Faltantes
        sheet.set_column("J:J", 15)  # Total reembolso

        # ===== ENCABEZADOS =====
        headers = [
            "Fecha trans",
            "Tarea",
            "Colaborador",
            "Orden de venta",
            "Servicio",
            "cantidad m2",
            "Precio unitario",
            "M2 Faltantes",
            "Total reembolso",
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, header_format)

        # ===== LÍNEAS =====
        row = 1
        for line in self.line_ids:
            sheet.write(row, 0, str(line.date or ""), text_format)
            sheet.write(row, 1, line.fs_sequence or "", text_format)
            sheet.write(row, 2, line.user_id.name or "", text_format)
            sheet.write(row, 3, line.sale_order_id or "", text_format)
            sheet.write(row, 4, line.product_code or "", text_format)
            sheet.write(row, 5, line.qty_m2 or "", text_format)
            sheet.write(row, 6, line.unit_rate or "", text_format)
            sheet.write(row, 7, line.pending_m2 or "", text_format)
            sheet.write(row, 8, line.fs_m2_cost or 0.0, amount_format)
            row += 1

        # ===== TOTAL =====
        sheet.write(row + 1, 7, "Total", total_label_format)
        sheet.write(row + 1, 8, self.total_amount or 0.0, total_amount_format)

        workbook.close()
        output.seek(0)
        xlsx_data = output.read()

        filename = "informe_reembolso_socio.xlsx"
        self.export_file = base64.b64encode(xlsx_data)
        self.export_filename = filename

        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=fs.timesheet.report.wizard"
                f"&id={self.id}&field=export_file&download=true&filename={filename}"
            ),
            "target": "self",
        }

    # ==========================
    #  Exportar a PDF
    # ==========================
    def action_export_pdf(self):
        self.ensure_one()
        return self.env.ref("fs_m2_cost.action_fs_timesheet_report_pdf").report_action(
            self
        )


class FSTimesheetReportLine(models.TransientModel):
    _name = "fs.timesheet.report.line"
    _description = "Línea informe reembolso socio"

    wizard_id = fields.Many2one(
        "fs.timesheet.report.wizard",
        string="Wizard",
        ondelete="cascade",
    )
    timesheet_id = fields.Many2one(
        "account.analytic.line",
        string="Registro de horas",
    )
    date = fields.Date(string="Fecha trans")
    task_id = fields.Many2one("project.task", string="Tarea")
    fs_sequence = fields.Char(string="Folio de tarea")
    user_id = fields.Many2one("res.users", string="Colaborador")
    product_id = fields.Many2one("product.product", string="Producto")
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea OV servicio",
    )
    sale_order_id = fields.Char(string="Orden de venta")
    product_code = fields.Char(string="Servicio")
    fs_m2_cost = fields.Float(string="Total reembolso")
    unit_rate = fields.Float(string="Tarifa unitaria")
    qty_m2 = fields.Float(string="Cantidad de m²")
    pending_m2 = fields.Float(
        string="M² pendientes de colocar",
        compute="_compute_pending_m2",
        store=False,
    )
    is_paid = fields.Boolean(
        string="Pagado",
        readonly=True,
        help="Indica si esta línea ya fue incluida en una factura de comisión.",
    )
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura de comisión",
        readonly=True,
    )
    
    task_stage_name = fields.Char(
        string="Etapa",
        readonly=True,
    )

    has_report = fields.Boolean(
        string="Firmado Reporte",
        readonly=True,
    )

    def action_view_task_report_portal(self):
        """Abrir la vista del portal de la tarea (para ver y firmar)"""
        self.ensure_one()
        
        if not self.task_id:
            raise UserError(_("No hay una tarea relacionada en esta línea."))
        
        task = self.task_id
        source = 'fsm'
        
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': task.get_portal_url(query_string=f'&source={source}')
        }

    @api.depends("qty_m2", "task_id", "wizard_id.line_ids.qty_m2")
    def _compute_pending_m2(self):
        """
        M² pendientes = fs_expected_m2 de la tarea - suma de qty_m2
        de todas las líneas del mismo wizard y misma tarea.
        """
        for line in self:
            task = line.task_id
            
            if not task or task.fs_expected_m2 is None:
                line.pending_m2 = 0.0
                continue

            # Sumar todos los m² de esta tarea en el mismo wizard
            total_placed = sum(
                l.qty_m2
                for l in (
                    line.wizard_id.line_ids or self.env["fs.timesheet.report.line"]
                )
                if l.task_id.id == task.id
            )
            line.pending_m2 = max((task.fs_expected_m2 or 0.0) - total_placed, 0.0)

    def action_open_task_images(self):
        self.ensure_one()
        if not self.task_id:
            raise UserError(_("No hay una tarea relacionada en esta línea."))

        return {
            "name": _("Evidencia fotográfica - %s") % (self.task_id.display_name,),
            "type": "ir.actions.act_window",
            "res_model": "fsm.task.image",
            "view_mode": "kanban",
            "views": [
                (self.env.ref("fs_m2_cost.view_fsm_task_image_kanban").id, "kanban")
            ],
            "domain": [("task_id", "=", self.task_id.id)],
            "target": "new",  # abre como popup
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
            },
        }
