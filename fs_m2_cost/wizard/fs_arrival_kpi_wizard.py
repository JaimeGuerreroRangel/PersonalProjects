from odoo import api, fields, models, _
from odoo.exceptions import UserError
from io import BytesIO
import base64

class FsArrivalKpiWizard(models.TransientModel):
    _name = 'fs.arrival.kpi.wizard'
    _description = 'KPI Llegadas Field Service'

    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
    user_ids = fields.Many2many(
        'res.users',
        string="Vendedores",
        help="Si se deja vacío, se incluyen todos los vendedores."
    )
    def action_export_excel(self):
        """Generar el Excel con KPIs por responsable de tarea (instalador)."""
        self.ensure_one()

        Task = self.env['project.task']
        Analytic = self.env['account.analytic.line']

        # ==========================
        # 1) Datos base
        # ==========================
        # Llegadas registradas en timesheet (fs_is_arrival = True)
        domain_lines = [
            ('fs_is_arrival', '=', True),
            ('task_id.date_deadline', '>=', self.date_from),
            ('task_id.date_deadline', '<=', self.date_to),
            ('task_id.sale_order_id', '!=', False),
        ]
        if self.user_ids:
            # Filtrar por responsable de tarea
            domain_lines.append(('task_id.user_ids', 'in', self.user_ids.ids))

        arrival_lines = Analytic.search(domain_lines, order='date, id')

        # Tareas no_show (sin llegada registrada)
        domain_no_show = [
            ('fs_arrival_status', '=', 'no_show'),
            ('date_deadline', '>=', self.date_from),
            ('date_deadline', '<=', self.date_to),
            ('sale_order_id', '!=', False),
        ]
        if self.user_ids:
            domain_no_show.append(('user_ids', 'in', self.user_ids.ids))

        no_show_tasks = Task.search(domain_no_show)

        # ==========================
        # 2) Agregados por RESPONSABLE y filas de detalle
        # ==========================
        # vendors = {user_id: {'name':..., 'on_time':..., 'late':..., 'no_show':..., 'delays': []}}
        vendors = {}
        detail_rows = []

        status_map = {
            'on_time': 'A tiempo',
            'late': 'Tarde',
            'no_show': 'No llegó',
        }

        # ---- Llegadas (on_time / late) desde account.analytic.line ----
        for line in arrival_lines:
            task = line.task_id
            so = task.sale_order_id if task else False
            if not task or not so:
                continue

            # Tomamos como responsable al primer usuario asignado a la tarea
            responsible = task.user_ids[:1]
            if not responsible:
                continue
            responsible = responsible[0]

            v = vendors.setdefault(responsible.id, {
                'name': responsible.name,
                'on_time': 0,
                'late': 0,
                'no_show': 0,
                'delays': [],
            })

            status_code = line.fs_arrival_status or task.fs_arrival_status or False
            delay_minutes = line.fs_delay_minutes or task.fs_delay_minutes or 0

            if status_code == 'on_time':
                v['on_time'] += 1
            elif status_code == 'late':
                v['late'] += 1
                if delay_minutes:
                    v['delays'].append(delay_minutes)

            # Fila de detalle
            fecha_pl = task.date_deadline and fields.Date.to_string(task.date_deadline) or ''
            hora_pl = task.date_deadline and fields.Datetime.to_string(task.date_deadline)[11:16] or ''
            llegada = line.fs_arrival_datetime or task.fs_arrival_datetime
            llegada_str = llegada and fields.Datetime.to_string(llegada) or ''
            cliente = so.partner_id.display_name if so.partner_id else ''
            tipo_tarea = task.worksheet_template_id.name or (task.project_id.name if task.project_id else '')
            installers = ', '.join(task.user_ids.mapped('name'))

            detail_rows.append([
                responsible.name,                       # 0 Responsable
                task.fs_sequence or task.name or '',    # 1 ID Tarea
                cliente,                                # 2 Cliente
                tipo_tarea,                             # 3 Tipo tarea
                fecha_pl,                               # 4 Fecha planeada
                hora_pl,                                # 5 Hora planeada
                llegada_str,                            # 6 Fecha/hora llegada
                status_map.get(status_code, ''),        # 7 Estatus llegada
                delay_minutes,                          # 8 Minutos retraso
                task.stage_id.name or '',               # 9 Estado tarea
                installers,                             # 10 Instalador(es)
                so.name or '',                          # 11 Orden de venta
            ])

        # ---- No show desde project.task ----
        for task in no_show_tasks:
            so = task.sale_order_id
            if not so:
                continue

            responsible = task.user_ids[:1]
            if not responsible:
                continue
            responsible = responsible[0]

            v = vendors.setdefault(responsible.id, {
                'name': responsible.name,
                'on_time': 0,
                'late': 0,
                'no_show': 0,
                'delays': [],
            })
            v['no_show'] += 1

            fecha_pl = task.date_deadline and fields.Date.to_string(task.date_deadline) or ''
            hora_pl = task.date_deadline and fields.Datetime.to_string(task.date_deadline)[11:16] or ''
            cliente = so.partner_id.display_name if so.partner_id else ''
            tipo_tarea = task.worksheet_template_id.name or (task.project_id.name if task.project_id else '')
            installers = ', '.join(task.user_ids.mapped('name'))
            delay_minutes = task.fs_delay_minutes or 0

            detail_rows.append([
                responsible.name,                       # 0 Responsable
                task.fs_sequence or task.name or '',    # 1 ID Tarea
                cliente,                                # 2 Cliente
                tipo_tarea,                             # 3 Tipo tarea
                fecha_pl,                               # 4 Fecha planeada
                hora_pl,                                # 5 Hora planeada
                '',                                     # 6 Fecha/hora llegada (vacío)
                status_map['no_show'],                  # 7 Estatus llegada
                delay_minutes,                          # 8 Minutos retraso
                task.stage_id.name or '',               # 9 Estado tarea
                installers,                             # 10 Instalador(es)
                so.name or '',                          # 11 Orden de venta
            ])

        # Ordenar detalle por fecha planeada y luego por ID de tarea
        detail_rows.sort(key=lambda r: (r[4] or '', r[1] or ''))

        # ==========================
        # 3) Generar Excel
        # ==========================
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("Falta el paquete python 'xlsxwriter' en el servidor."))

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ==== FORMATOS ====
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#305496',
            'font_color': '#FFFFFF',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        percent_format = workbook.add_format({
            'num_format': '0.0%',
            'align': 'center',
        })
        number_format = workbook.add_format({
            'num_format': '0.00',
        })
        status_on_time_fmt = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        status_late_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
        status_no_show_fmt = workbook.add_format({'bg_color': '#F8CBAD', 'font_color': '#9C0006'})

        # ==========================
        # Hoja DETALLE
        # ==========================
        sheet_det = workbook.add_worksheet('Detalle')
        headers_det = [
            'Responsable', 'ID Tarea', 'Cliente', 'Tipo tarea',
            'Fecha planeada', 'Hora planeada',
            'Fecha/hora llegada', 'Estatus llegada',
            'Minutos retraso', 'Estado tarea', 'Instalador(es)', 'Orden de venta',
        ]

        sheet_det.set_row(0, 22, header_format)
        for col, h in enumerate(headers_det):
            sheet_det.write(0, col, h, header_format)

        sheet_det.set_column(0, 0, 20)   # Responsable
        sheet_det.set_column(1, 1, 18)   # ID Tarea
        sheet_det.set_column(2, 2, 25)   # Cliente
        sheet_det.set_column(3, 3, 25)   # Tipo tarea
        sheet_det.set_column(4, 6, 18)   # Fechas / horas
        sheet_det.set_column(7, 7, 15)   # Estatus llegada
        sheet_det.set_column(8, 8, 18)   # Minutos retraso
        sheet_det.set_column(9, 10, 20)  # Estado / Instalador(es)
        sheet_det.set_column(11, 11, 18) # Orden de venta

        sheet_det.freeze_panes(1, 0)
        sheet_det.autofilter(0, 0, 0, len(headers_det) - 1)

        row = 1
        for vals in detail_rows:
            for col, val in enumerate(vals):
                if col == 8 and isinstance(val, (int, float)):
                    sheet_det.write(row, col, val, number_format)
                else:
                    sheet_det.write(row, col, val)
            row += 1

        last_detail_row = row - 1
        if last_detail_row >= 1:
            sheet_det.conditional_format(1, 7, last_detail_row, 7, {
                'type': 'cell', 'criteria': '==', 'value': '"A tiempo"', 'format': status_on_time_fmt,
            })
            sheet_det.conditional_format(1, 7, last_detail_row, 7, {
                'type': 'cell', 'criteria': '==', 'value': '"Tarde"', 'format': status_late_fmt,
            })
            sheet_det.conditional_format(1, 7, last_detail_row, 7, {
                'type': 'cell', 'criteria': '==', 'value': '"No llegó"', 'format': status_no_show_fmt,
            })

        # ==========================
        # Hoja RESUMEN
        # ==========================
        sheet_res = workbook.add_worksheet('Resumen')
        headers_res = [
            'Responsable', 'Tareas totales', 'A tiempo', 'Tarde',
            'No llegó', '% A tiempo', '% Tarde', '% No llegó',
            'Retraso promedio (min)',
        ]

        sheet_res.set_row(0, 22, header_format)
        for col, h in enumerate(headers_res):
            sheet_res.write(0, col, h, header_format)

        sheet_res.set_column(0, 0, 20)
        sheet_res.set_column(1, 4, 15)
        sheet_res.set_column(5, 7, 12)
        sheet_res.set_column(8, 8, 22)
        sheet_res.freeze_panes(1, 0)

        row = 1
        for _, data in vendors.items():
            total = data['on_time'] + data['late'] + data['no_show']
            avg_delay = round(sum(data['delays']) / len(data['delays']), 2) if data['delays'] else 0.0

            vals = [
                data['name'],
                total,
                data['on_time'],
                data['late'],
                data['no_show'],
                None,
                None,
                None,
                avg_delay,
            ]
            for col, val in enumerate(vals):
                if col == 8 and isinstance(val, (int, float)):
                    sheet_res.write(row, col, val, number_format)
                else:
                    sheet_res.write(row, col, val)

            sheet_res.write_formula(row, 5, f"=IF(B{row+1}=0,0,C{row+1}/B{row+1})", percent_format)
            sheet_res.write_formula(row, 6, f"=IF(B{row+1}=0,0,D{row+1}/B{row+1})", percent_format)
            sheet_res.write_formula(row, 7, f"=IF(B{row+1}=0,0,E{row+1}/B{row+1})", percent_format)
            row += 1

        # ==========================
        # Gráfico
        # ==========================
        if vendors:
            chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
            last_row = row - 1
            categories_range = f"=Resumen!$A$2:$A${last_row}"

            chart.add_series({
                'name': 'A tiempo',
                'categories': categories_range,
                'values': f"=Resumen!$C$2:$C${last_row}",
            })
            chart.add_series({
                'name': 'Tarde',
                'categories': categories_range,
                'values': f"=Resumen!$D$2:$D${last_row}",
            })
            chart.add_series({
                'name': 'No llegó',
                'categories': categories_range,
                'values': f"=Resumen!$E$2:$E${last_row}",
            })

            chart.set_title({'name': 'Llegadas por responsable'})
            chart.set_x_axis({'name': 'Responsable'})
            chart.set_y_axis({'name': 'Número de visitas'})

            sheet_res.insert_chart('K2', chart, {'x_offset': 10, 'y_offset': 10})

        workbook.close()
        output.seek(0)
        file_data = output.read()

        attachment = self.env['ir.attachment'].create({
            'name': 'kpi_llegadas_fs.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'res_model': 'fs.arrival.kpi.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=1",
            'target': 'self',
        }
