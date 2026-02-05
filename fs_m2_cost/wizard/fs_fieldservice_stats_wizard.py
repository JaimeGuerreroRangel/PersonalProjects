# -*- coding: utf-8 -*-
import base64
import io
from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError


class FsFieldserviceStatsWizard(models.TransientModel):
    _name = "fs.fieldservice.stats.wizard"
    _description = "Resumen Field Service (M2 & Tareas)"

    # Filtros
    date_from = fields.Date(string="Desde", required=True, default=fields.Date.today)
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.today)

    # Resumen global
    m2_installed_total = fields.Float(string="M² instalados", readonly=True)

    measurement_count = fields.Integer(
        string="Tomas de medida realizadas", readonly=True
    )
    measurement_sale_count = fields.Integer(
        string="Tomas de medida con venta", readonly=True
    )

    installation_count = fields.Integer(string="Colocaciones realizadas", readonly=True)
    installation_on_time = fields.Integer(string="Colocaciones a tiempo", readonly=True)
    installation_late = fields.Integer(string="Colocaciones tarde", readonly=True)
    installation_no_show = fields.Integer(
        string="Colocaciones sin llegada", readonly=True
    )

    # KPIs extra para reporte operativo
    m2_expected_total = fields.Float(string="M² esperados", readonly=True)
    m2_pending_total = fields.Float(string="M² pendientes (global)", readonly=True)
    on_time_rate = fields.Float(string="% On-time (global)", readonly=True)

    # Resumen por colocador
    line_ids = fields.One2many(
        "fs.fieldservice.stats.line",
        "wizard_id",
        string="Resumen por colocador",
        readonly=True,
    )

    # Detalles (popups) - IMPORTANTE: tablas rel distintas
    measurement_task_ids = fields.Many2many(
        "project.task",
        "fs_stats_measurement_task_rel",
        "wizard_id",
        "task_id",
        string="Tomas de medida (todas)",
        readonly=True,
    )
    measurement_sale_task_ids = fields.Many2many(
        "project.task",
        "fs_stats_measurement_sale_task_rel",
        "wizard_id",
        "task_id",
        string="Tomas de medida con venta",
        readonly=True,
    )
    installation_task_ids = fields.Many2many(
        "project.task",
        "fs_stats_installation_task_rel",
        "wizard_id",
        "task_id",
        string="Colocaciones (todas)",
        readonly=True,
    )
    installation_on_time_ids = fields.Many2many(
        "project.task",
        "fs_stats_installation_on_time_task_rel",
        "wizard_id",
        "task_id",
        string="Colocaciones a tiempo",
        readonly=True,
    )
    installation_late_ids = fields.Many2many(
        "project.task",
        "fs_stats_installation_late_task_rel",
        "wizard_id",
        "task_id",
        string="Colocaciones tarde",
        readonly=True,
    )
    installation_no_show_ids = fields.Many2many(
        "project.task",
        "fs_stats_installation_no_show_task_rel",
        "wizard_id",
        "task_id",
        string="Colocaciones sin llegada",
        readonly=True,
    )
    m2_timesheet_ids = fields.Many2many(
        "account.analytic.line",
        "fs_stats_m2_timesheet_rel",
        "wizard_id",
        "aal_id",
        string="Horas con m² instalados",
        readonly=True,
    )

    # ====== IMÁGENES PARA REPORTE PDF (PNG base64) ======
    chart_punctuality_png = fields.Binary(string="Chart puntualidad", readonly=True)
    chart_ontime_trend_png = fields.Binary(
        string="Chart tendencia on-time", readonly=True
    )
    chart_m2_growth_png = fields.Binary(string="Chart crecimiento m²", readonly=True)
    chart_installer_top_png = fields.Binary(
        string="Chart top m² por colocador", readonly=True
    )
    chart_installer_stack_png = fields.Binary(
        string="Chart instalados vs pendientes", readonly=True
    )
    chart_expected_vs_installed_png = fields.Binary(
        string="Chart esperado vs instalado", readonly=True
    )

    # -------------------------------------------------------------------------
    # Helpers de gráficas (matplotlib)
    # -------------------------------------------------------------------------
    def _mpl_available(self):
        try:
            import matplotlib  # noqa

            return True
        except Exception:
            return False

    def _mpl_setup(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt

    def _fig_to_png_bytes(self, fig):
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=140)
        return buf.getvalue()

    def _make_donut_png(self, labels, values, title):
        """
        Donut chart con:
        - leyenda (explica qué color corresponde a qué categoría)
        - sin labels pegados (labels=None)
        - espaciado superior para que no se encime el título/leyenda
        - filtrado opcional de categorías en 0 (para evitar ruido)
        """
        try:
            plt = self._mpl_setup()
        except Exception:
            return b""

        # Opcional: elimina categorías en cero para evitar encimados/ruido
        filtered = [(l, v) for l, v in zip(labels, values) if v]
        if not filtered:
            filtered = [("Sin datos", 1)]
        labels, values = zip(*filtered)

        # Tamaño controlado (mejor para PDF)
        fig = plt.figure(figsize=(5.2, 3.2))
        ax = fig.add_subplot(111)

        wedges, _texts, _autotexts = ax.pie(
            values,
            labels=None,  # evitamos labels alrededor (se usa leyenda)
            autopct="%1.0f%%",
            startangle=90,
            pctdistance=0.72,  # porcentaje un poco más hacia el centro
        )

        # Donut
        centre_circle = plt.Circle((0, 0), 0.55, fc="white")
        ax.add_artist(centre_circle)

        # Leyenda: explica colores
        ax.legend(
            wedges,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.12),  # abajo del gráfico
            ncol=min(3, len(labels)),
            frameon=False,
            fontsize=9,
        )

        # Título con padding para separar del contenido superior
        ax.set_title(title, pad=18)

        # Ajuste para dejar aire arriba (evita encimados en PDF)
        fig.subplots_adjust(top=0.95, bottom=0.28)

        ax.axis("equal")

        png = self._fig_to_png_bytes(fig)
        plt.close(fig)
        return png

    def _make_line_png(self, x_labels, y_values, title, y_label):
        try:
            plt = self._mpl_setup()
        except Exception:
            return b""

        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(list(range(len(x_labels))), y_values, marker="o")
        ax.set_title(title)
        ax.set_ylabel(y_label)
        ax.set_xticks(list(range(len(x_labels))))
        ax.set_xticklabels(x_labels, rotation=45, ha="right")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5)
        png = self._fig_to_png_bytes(fig)
        plt.close(fig)
        return png

    def _make_bar_png(self, labels, values, title, y_label):
        try:
            plt = self._mpl_setup()
        except Exception:
            return b""

        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.bar(labels, values)
        ax.set_title(title)
        ax.set_ylabel(y_label)
        ax.tick_params(axis="x", labelrotation=45)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5)
        png = self._fig_to_png_bytes(fig)
        plt.close(fig)
        return png

    def _make_stacked_bar_png(
        self, labels, installed_vals, pending_vals, title, y_label
    ):
        try:
            plt = self._mpl_setup()
        except Exception:
            return b""

        fig = plt.figure()
        ax = fig.add_subplot(111)

        ax.bar(labels, installed_vals, label="Instalado")
        ax.bar(labels, pending_vals, bottom=installed_vals, label="Pendiente")

        ax.set_title(title)
        ax.set_ylabel(y_label)
        ax.tick_params(axis="x", labelrotation=45)
        ax.legend()
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5)

        png = self._fig_to_png_bytes(fig)
        plt.close(fig)
        return png

    def _week_start(self, d):
        """Regresa el lunes de la semana de la fecha d."""
        if not d:
            return None
        return d - timedelta(days=d.weekday())

    def _iter_weeks(self, d_from, d_to):
        """Lista de inicios de semana (lunes) entre d_from y d_to."""
        if not d_from or not d_to:
            return []
        cur = self._week_start(d_from)
        end = self._week_start(d_to)
        res = []
        while cur <= end:
            res.append(cur)
            cur = cur + timedelta(days=7)
        return res

    def _top_n_with_others(self, labels, values, n=10, others_label="Otros"):
        """Reduce arrays a Top N + Otros."""
        if len(labels) <= n:
            return labels, values
        pairs = list(zip(labels, values))
        pairs.sort(key=lambda x: x[1], reverse=True)
        top = pairs[:n]
        rest = pairs[n:]
        top_labels = [x[0] for x in top]
        top_values = [x[1] for x in top]
        rest_sum = sum(x[1] for x in rest)
        if rest_sum:
            top_labels.append(others_label)
            top_values.append(rest_sum)
        return top_labels, top_values

    # -------------------------------------------------------------------------
    # Cálculo principal
    # -------------------------------------------------------------------------
    def action_compute(self):
        """Calcular KPIs según el rango de fechas + generar charts para PDF."""
        self.ensure_one()

        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError(_("La fecha 'Desde' no puede ser mayor que 'Hasta'."))

        Task = self.env["project.task"]
        Analytic = self.env["account.analytic.line"]

        # 1) Tareas en rango por date_deadline
        domain_tasks = []
        if self.date_from:
            domain_tasks.append(("date_deadline", ">=", self.date_from))
        if self.date_to:
            domain_tasks.append(("date_deadline", "<=", self.date_to))

        tasks = Task.search(domain_tasks)

        if not tasks:
            self.write(
                {
                    "m2_installed_total": 0.0,
                    "m2_expected_total": 0.0,
                    "m2_pending_total": 0.0,
                    "on_time_rate": 0.0,
                    "measurement_count": 0,
                    "measurement_sale_count": 0,
                    "installation_count": 0,
                    "installation_on_time": 0,
                    "installation_late": 0,
                    "installation_no_show": 0,
                    "line_ids": [(5, 0, 0)],
                    "chart_punctuality_png": False,
                    "chart_ontime_trend_png": False,
                    "chart_m2_growth_png": False,
                    "chart_installer_top_png": False,
                    "chart_installer_stack_png": False,
                    "chart_expected_vs_installed_png": False,
                }
            )
            self.measurement_task_ids = [(5, 0, 0)]
            self.measurement_sale_task_ids = [(5, 0, 0)]
            self.installation_task_ids = [(5, 0, 0)]
            self.installation_on_time_ids = [(5, 0, 0)]
            self.installation_late_ids = [(5, 0, 0)]
            self.installation_no_show_ids = [(5, 0, 0)]
            self.m2_timesheet_ids = [(5, 0, 0)]

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "view_id": self.env.ref(
                    "fs_m2_cost.fs_fieldservice_stats_wizard_view"
                ).id,
                "target": "current",
            }

        # 2) Timesheets con m² para estas tareas
        domain_aal_m2 = [
            ("task_id", "in", tasks.ids),
            ("fs_m2_cost", ">", 0),
        ]
        timesheets_m2 = Analytic.search(domain_aal_m2)

        # task_id -> m2 instalados
        m2_by_task = {}
        m2_ts_ids = set()
        for ts in timesheets_m2:
            if not ts.task_id:
                continue
            tid = ts.task_id.id
            m2_by_task.setdefault(tid, 0.0)
            m2_by_task[tid] += ts.fs_m2_real or 0.0
            m2_ts_ids.add(ts.id)

        # 3) Contadores globales + acumulados operativos
        total_m2_all = 0.0

        total_expected_install = 0.0
        total_installed_install = 0.0

        meas = meas_sale = 0
        inst = inst_on_time = inst_late = inst_no_show = 0

        installer_map = {}  # por colocador (m² asignados)
        meas_tasks = set()
        meas_sale_tasks = set()
        inst_tasks = set()
        inst_on_time_tasks = set()
        inst_late_tasks = set()
        inst_no_show_tasks = set()

        # Para tendencias semanales (operativo)
        weeks = self._iter_weeks(self.date_from, self.date_to)
        ontime_by_week = {w: {"total": 0, "on_time": 0} for w in weeks}
        m2_by_week = {w: 0.0 for w in weeks}

        for task in tasks:
            task_m2 = m2_by_task.get(task.id, 0.0)
            expected = task.fs_expected_m2 or 0.0
            pending = max(expected - task_m2, 0.0)

            total_m2_all += task_m2

            sale = task.sale_order_id
            sale_line = getattr(task, "fs_related_sale_line_id", False)
            product = (
                sale_line.product_id if (sale_line and sale_line.product_id) else False
            )

            is_eval_product = bool(
                product and getattr(product, "fs_is_evaluation", False)
            )
            is_install_product = bool(
                product and getattr(product, "fs_is_installation", False)
            )

            seq = task.fs_sequence or ""
            is_measure = bool(seq.startswith("STM") or is_eval_product)
            is_install = bool(seq.startswith("SCO") or is_install_product)

            # Tomas
            if is_measure:
                meas += 1
                meas_tasks.add(task.id)
                if sale and sale.state in ("sale", "done"):
                    meas_sale += 1
                    meas_sale_tasks.add(task.id)

            # Colocaciones
            if is_install:
                inst += 1
                inst_tasks.add(task.id)

                # global esperado vs instalado (solo instalaciones)
                total_expected_install += expected
                total_installed_install += task_m2

                # puntualidad
                st = task.fs_arrival_status
                if st == "on_time":
                    inst_on_time += 1
                    inst_on_time_tasks.add(task.id)
                elif st == "late":
                    inst_late += 1
                    inst_late_tasks.add(task.id)
                elif st == "no_show":
                    inst_no_show += 1
                    inst_no_show_tasks.add(task.id)

                # tendencia semanal por date_deadline
                d = task.date_deadline
                w = self._week_start(d) if d else None
                if w in ontime_by_week:
                    ontime_by_week[w]["total"] += 1
                    if st == "on_time":
                        ontime_by_week[w]["on_time"] += 1
                if w in m2_by_week:
                    m2_by_week[w] += task_m2

            # Resumen por colocador (m² asignados por task.user_ids)
            task_relevant_for_installer = is_install and (task_m2 > 0 or expected > 0)
            if task_relevant_for_installer:
                for user in task.user_ids:
                    data = installer_map.setdefault(
                        user.id,
                        {
                            "user_id": user.id,
                            "task_ids": set(),
                            "m2_installed": 0.0,
                            "m2_pending": 0.0,
                        },
                    )
                    data["task_ids"].add(task.id)
                    data["m2_installed"] += task_m2
                    data["m2_pending"] += pending

        # 4) Escribir totales
        pending_global_install = max(
            total_expected_install - total_installed_install, 0.0
        )
        on_time_rate = (inst_on_time / inst * 100.0) if inst else 0.0

        self.write(
            {
                "m2_installed_total": total_m2_all,
                "m2_expected_total": total_expected_install,
                "m2_pending_total": pending_global_install,
                "on_time_rate": on_time_rate,
                "measurement_count": meas,
                "measurement_sale_count": meas_sale,
                "installation_count": inst,
                "installation_on_time": inst_on_time,
                "installation_late": inst_late,
                "installation_no_show": inst_no_show,
            }
        )

        # 5) Líneas por colocador
        self.line_ids.unlink()
        lines_vals = []
        for data in installer_map.values():
            m2_installed = data["m2_installed"]
            m2_pending = data["m2_pending"]
            tasks_done = len(data["task_ids"]) or 0
            m2_per_task = (m2_installed / tasks_done) if tasks_done else 0.0
            completion_rate = (
                (m2_installed / (m2_installed + m2_pending) * 100.0)
                if (m2_installed + m2_pending)
                else 0.0
            )

            lines_vals.append(
                (
                    0,
                    0,
                    {
                        "user_id": data["user_id"],
                        "tasks_done": tasks_done,
                        "m2_installed": m2_installed,
                        "m2_pending": m2_pending,
                        "m2_per_task": m2_per_task,
                        "completion_rate": completion_rate,
                    },
                )
            )
        if lines_vals:
            self.line_ids = lines_vals

        # 6) Sets para popups
        self.measurement_task_ids = [(6, 0, list(meas_tasks))]
        self.measurement_sale_task_ids = [(6, 0, list(meas_sale_tasks))]
        self.installation_task_ids = [(6, 0, list(inst_tasks))]
        self.installation_on_time_ids = [(6, 0, list(inst_on_time_tasks))]
        self.installation_late_ids = [(6, 0, list(inst_late_tasks))]
        self.installation_no_show_ids = [(6, 0, list(inst_no_show_tasks))]
        self.m2_timesheet_ids = [(6, 0, list(m2_ts_ids))]

        # 7) Generación de charts (si matplotlib existe)
        charts = {
            "chart_punctuality_png": False,
            "chart_ontime_trend_png": False,
            "chart_m2_growth_png": False,
            "chart_installer_top_png": False,
            "chart_installer_stack_png": False,
            "chart_expected_vs_installed_png": False,
        }

        if self._mpl_available():
            # 7.1 Donut puntualidad
            donut_labels = ["A tiempo", "Tarde", "Sin llegada"]
            donut_vals = [inst_on_time, inst_late, inst_no_show]
            png = self._make_donut_png(
                donut_labels, donut_vals, "Puntualidad de colocaciones"
            )
            charts["chart_punctuality_png"] = base64.b64encode(png) if png else False

            # 7.2 Tendencia % on-time semanal
            week_labels = [w.strftime("%Y-%m-%d") for w in weeks]
            ontime_rates = []
            for w in weeks:
                total = ontime_by_week[w]["total"]
                on_time = ontime_by_week[w]["on_time"]
                ontime_rates.append((on_time / total * 100.0) if total else 0.0)
            png = self._make_line_png(
                week_labels, ontime_rates, "Tendencia semanal % On-time", "% On-time"
            )
            charts["chart_ontime_trend_png"] = base64.b64encode(png) if png else False

            # 7.3 Crecimiento m² acumulado semanal
            cum = 0.0
            m2_cum = []
            for w in weeks:
                cum += m2_by_week.get(w) or 0.0
                m2_cum.append(cum)
            png = self._make_line_png(
                week_labels,
                m2_cum,
                "Crecimiento (acumulado) m² instalados",
                "m² acumulados",
            )
            charts["chart_m2_growth_png"] = base64.b64encode(png) if png else False

            # 7.4 Top m² por colocador (barras)
            # usa line_ids ya calculado (m² asignados)
            sorted_lines = self.line_ids.sorted(
                key=lambda l: l.m2_installed, reverse=True
            )
            labels = [l.user_id.name for l in sorted_lines]
            values = [l.m2_installed for l in sorted_lines]
            labels, values = self._top_n_with_others(
                labels, values, n=10, others_label="Otros"
            )
            png = self._make_bar_png(
                labels, values, "Top colocadores por m² instalados", "m² instalados"
            )
            charts["chart_installer_top_png"] = base64.b64encode(png) if png else False

            # 7.5 Instalados vs pendientes por colocador (barras apiladas)
            # también top 10 por installed (para que el PDF sea legible)
            top_lines = sorted_lines[:10]
            labels = [l.user_id.name for l in top_lines]
            installed_vals = [l.m2_installed for l in top_lines]
            pending_vals = [l.m2_pending for l in top_lines]
            png = self._make_stacked_bar_png(
                labels,
                installed_vals,
                pending_vals,
                "Instalados vs pendientes (Top 10)",
                "m²",
            )
            charts["chart_installer_stack_png"] = (
                base64.b64encode(png) if png else False
            )

            # 7.6 Esperado vs instalado global (barra simple con 2 columnas)
            labels = ["Esperado", "Instalado"]
            values = [total_expected_install, total_installed_install]
            png = self._make_bar_png(
                labels, values, "Global: Esperado vs Instalado (instalaciones)", "m²"
            )
            charts["chart_expected_vs_installed_png"] = (
                base64.b64encode(png) if png else False
            )

        self.write(charts)

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("fs_m2_cost.fs_fieldservice_stats_wizard_view").id,
            "target": "new",
        }

    # === ACCIONES POPUP ===
    def _open_tasks_action(self, title, tasks):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "project.task",
            "view_mode": "list,form",
            "target": "new",
            "domain": [("id", "in", tasks.ids)],
        }

    def _open_timesheets_action(self, title, timesheets):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "account.analytic.line",
            "view_mode": "list,form",
            "target": "new",
            "domain": [("id", "in", timesheets.ids)],
        }

    def action_open_installations(self):
        return self._open_tasks_action(
            _("Colocaciones realizadas"), self.installation_task_ids
        )

    def action_open_installations_on_time(self):
        return self._open_tasks_action(
            _("Colocaciones a tiempo"), self.installation_on_time_ids
        )

    def action_open_installations_late(self):
        return self._open_tasks_action(
            _("Colocaciones tarde"), self.installation_late_ids
        )

    def action_open_installations_no_show(self):
        return self._open_tasks_action(
            _("Colocaciones sin llegada"), self.installation_no_show_ids
        )

    def action_open_measurements(self):
        return self._open_tasks_action(
            _("Tomas de medida realizadas"), self.measurement_task_ids
        )

    def action_open_measurements_with_sale(self):
        return self._open_tasks_action(
            _("Tomas de medida con venta"), self.measurement_sale_task_ids
        )

    def action_open_m2_timesheets(self):
        return self._open_timesheets_action(
            _("Horas con m² instalados"), self.m2_timesheet_ids
        )

    def action_export_pdf_status(self):
        """Imprimir el resumen en PDF (con gráficas)."""
        self.ensure_one()
        if (not self.line_ids) or (not self.chart_punctuality_png):
            self.action_compute()
        return self.env.ref(
            "fs_m2_cost.action_report_fs_fieldservice_stats_charts"
        ).report_action(self)


class FsFieldserviceStatsLine(models.TransientModel):
    _name = "fs.fieldservice.stats.line"
    _description = "Resumen por colocador"
    _order = "m2_installed desc"

    wizard_id = fields.Many2one(
        "fs.fieldservice.stats.wizard",
        string="Wizard",
        ondelete="cascade",
    )
    user_id = fields.Many2one("res.users", string="Colocador", required=True)

    tasks_done = fields.Integer(string="Tareas realizadas")
    m2_installed = fields.Float(string="M² instalados", digits=(16, 2))
    m2_pending = fields.Float(string="M² pendientes", digits=(16, 2))

    # KPIs operativos por colocador
    m2_per_task = fields.Float(string="m² / tarea", digits=(16, 2))
    completion_rate = fields.Float(string="% Cumplimiento", digits=(16, 2))
