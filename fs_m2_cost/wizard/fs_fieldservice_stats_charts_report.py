# -*- coding: utf-8 -*-
from odoo import api, models, _


class ReportFsFieldserviceStatsCharts(models.AbstractModel):
    _name = "report.fs_m2_cost.report_fs_fieldservice_stats_charts"
    _description = "FS Resumen Field Service (Charts + Detalle por colaborador)"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["fs.fieldservice.stats.wizard"].browse(docids)

        # Asegurar que el wizard ya tenga todo calculado (line_ids, sets, charts)
        for w in docs:
            if not w.line_ids or not w.chart_punctuality_png:
                w.action_compute()

        detail = self._build_task_detail_by_installer(docs[:1])

        return {
            "doc_ids": docids,
            "doc_model": "fs.fieldservice.stats.wizard",
            "docs": docs,
            "task_detail_by_installer": detail,  # <- lo consume el QWeb
        }

    def _build_task_detail_by_installer(self, wizard):
        """Devuelve: [{'installer_name':..., 'rows':[...], 'totals':{...}}, ...]"""
        if not wizard:
            return []

        wizard = wizard[0]
        Task = self.env["project.task"]
        AAL = self.env["account.analytic.line"]

        # Preferimos usar el set ya calculado por el wizard (instalaciones)
        tasks = wizard.installation_task_ids
        if not tasks:
            # fallback: reusar rango si por alguna razón no está calculado
            domain = []
            if wizard.date_from:
                domain.append(("date_deadline", ">=", wizard.date_from))
            if wizard.date_to:
                domain.append(("date_deadline", "<=", wizard.date_to))
            tasks = Task.search(domain)

        if not tasks:
            return []

        # m² instalados por tarea desde timesheets
        # (compatible con tu código: usa fs_m2_real si existe, si no fs_m2_cost)
        timesheets = AAL.search([
            ("task_id", "in", tasks.ids),
            ("fs_m2_cost", ">", 0),
        ])
        m2_by_task = {}
        for ts in timesheets:
            if not ts.task_id:
                continue
            v = getattr(ts, "fs_m2_real", None)
            if v is None:
                v = ts.fs_m2_cost or 0.0
            m2_by_task[ts.task_id.id] = m2_by_task.get(ts.task_id.id, 0.0) + (v or 0.0)

        grouped = {}

        def _get_sale(task):
            sale = getattr(task, "sale_order_id", False)
            if sale:
                return sale
            sale_line = getattr(task, "fs_related_sale_line_id", False)
            return sale_line.order_id if sale_line else False

        for task in tasks:
            installed = m2_by_task.get(task.id, 0.0)
            expected = task.fs_expected_m2 or 0.0
            pending = max(expected - installed, 0.0)

            sale = _get_sale(task)
            sale_line = getattr(task, "fs_related_sale_line_id", False)
            product = sale_line.product_id if (sale_line and sale_line.product_id) else False

            customer = ""
            if getattr(task, "partner_id", False) and task.partner_id:
                customer = task.partner_id.name or ""
            elif sale and sale.partner_id:
                customer = sale.partner_id.name or ""

            row = {
                "customer": customer,
                "sale_order": sale.name if sale else "",
                "service": product.display_name if product else "",
                "task_ref": (task.fs_sequence or task.name or ""),
                "task_stage": (task.stage_id.name if task.stage_id else ""),
                "installed_m2": installed,
                "expected_m2": expected,
                "pending_m2": pending,
            }

            users = task.user_ids
            if not users:
                key = 0
                bucket = grouped.setdefault(key, {
                    "installer_name": _("Sin asignar"),
                    "rows": [],
                    "totals": {"installed_m2": 0.0, "pending_m2": 0.0},
                })
                bucket["rows"].append(row)
                bucket["totals"]["installed_m2"] += installed
                bucket["totals"]["pending_m2"] += pending
            else:
                for u in users:
                    key = u.id
                    bucket = grouped.setdefault(key, {
                        "installer_name": u.name,
                        "rows": [],
                        "totals": {"installed_m2": 0.0, "pending_m2": 0.0},
                    })
                    bucket["rows"].append(row)
                    bucket["totals"]["installed_m2"] += installed
                    bucket["totals"]["pending_m2"] += pending

        # Ordenar colaboradores y filas
        result = []
        for _k, data in sorted(grouped.items(), key=lambda it: (it[1]["installer_name"] or "")):
            data["rows"].sort(key=lambda r: (r["sale_order"] or "", r["task_ref"] or ""))
            result.append(data)
        return result
