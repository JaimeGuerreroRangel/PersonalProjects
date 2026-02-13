from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from odoo.tools.float_utils import float_compare 
from odoo.exceptions import ValidationError

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    fs_m2_real = fields.Float(
        string="M2 reales",
        help="M2 instalados reales en este registro de tiempo.",
        store=True,
    )

    fs_progress_pct = fields.Float(
        string="Avance %",
        help="Porcentaje de avance en m2 respecto a lo planeado.",
        readonly=True,
        store=True,
        compute="_compute_fs_cost_and_progress",
    )

    fs_m2_cost = fields.Float(
        string="Costo M2",
        help="Costo calculado para estos m2 reales.",
        readonly=False,
        store=True,
        compute="_compute_fs_cost_and_progress",
    )

    fs_tarifa_type = fields.Selection(
        [
            ("a", "Tarifa A"),
            ("b", "Tarifa B"),
        ],
        string="Tipo de tarifa aplicada",
        help="Indica si se usó la tarifa A o la tarifa B según el usuario.",
        readonly=True,
        store=True,
        compute="_compute_fs_cost_and_progress",
    )

    fs_commission_move_id = fields.Many2one(
        "account.move",
        string="Factura comisión FS",
        ondelete="set null",  # IMPORTANTE: si se borra la factura, esto se limpia
        readonly=True,
        copy=False,
    )
    fs_commission_paid = fields.Boolean(
        string="Comisión FS pagada",
        store=True, 
        readonly=False,
        copy=False,
    )
        
    @api.depends("fs_commission_move_id", "fs_commission_move_id.state", "fs_commission_move_id.move_type")
    def _compute_fs_commission_paid(self):
        for line in self:
            move = line.fs_commission_move_id
            line.fs_commission_paid = bool(
                move
                and move.move_type == "in_invoice"
                and move.state != "cancel"
            )
        
    @api.depends("fs_m2_real", "task_id", "user_id")
    def _compute_fs_cost_and_progress(self):
        FieldServiceRate = self.env["field.service.rate"]

        for line in self:
            cost = 0.0
            progress = 0.0
            tarifa_type_val = False

            task = line.task_id
            user = line.user_id

            # Si falta algo clave, ponemos todo en cero
            if not task or not user or not line.fs_m2_real:
                line.fs_m2_cost = 0.0
                line.fs_progress_pct = 0.0
                line.fs_tarifa_type = False
                continue

            # Servicio relacionado a la tarea
            service_tmpl = False
            if task.fs_related_sale_line_id and task.fs_related_sale_line_id.product_id:
                service_tmpl = task.fs_related_sale_line_id.product_id.product_tmpl_id
            
            # Si no hay OV
            elif task.fs_service_template_id:
                service_tmpl = task.fs_service_template_id

            if not service_tmpl:
                line.fs_m2_cost = 0.0
                line.fs_progress_pct = 0.0
                line.fs_tarifa_type = False
                continue

            # Buscar tabulador para el servicio
            tab = FieldServiceRate.search(
                [("service_id", "=", service_tmpl.id)],
                limit=1,
            )
            if not tab:
                line.fs_m2_cost = 0.0
                line.fs_progress_pct = 0.0
                line.fs_tarifa_type = False
                continue

            # Seleccionar tarifa según el usuario (Tarifa A o B)
            tariff_type = user.tariff_type or "a"
            tarifa_type_val = tariff_type
            tarifa = tab.tarifa_a if tariff_type == "a" else tab.tarifa_b

            # 💰 NUEVA FÓRMULA:
            # Costo = M2 reales * tarifa (A o B) del tabulador
            cost = line.fs_m2_real * tarifa

            # Avance: M2 reales / M2 esperados (desde la tarea)
            expected_m2 = task.fs_expected_m2 or 0.0
            if expected_m2:
                progress = (line.fs_m2_real / expected_m2) * 100.0

            line.fs_m2_cost = cost
            line.fs_progress_pct = progress
            line.fs_tarifa_type = tarifa_type_val


    @api.onchange("fs_m2_real", "task_id", "user_id")
    def _onchange_fs_m2_real(self):
        """
        Para que el cálculo se vea en pantalla en cuanto se captura,
        usamos el mismo método de compute en onchange.
        """
        self._compute_fs_cost_and_progress()

    @api.constrains("fs_m2_cost", "task_id")
    def _check_fs_m2_cost_not_exceed_task_expected(self):
        """
        Valida que la suma de fs_m2_cost de todas las líneas de la tarea
        no supere fs_expected_m2 de project.task.
        """
        for line in self:
            task = line.task_id
            if not task or not task.fs_expected_m2:
                # Si la tarea no tiene límite definido, no validamos
                continue

            # Sumar todos los m2 de la tarea (excluyendo la línea actual)
            other_lines = self.search([
                ("task_id", "=", task.id),
                ("id", "!=", line.id),
                ("fs_m2_real", "!=", False),
            ])
            total_m2 = sum(other_lines.mapped("fs_m2_real")) + (line.fs_m2_real or 0.0)

            # Comparar con un poco de tolerancia en decimales (2)
            if float_compare(
                total_m2,
                task.fs_expected_m2,
                precision_digits=2,
            ) == 1:
                raise ValidationError(_(
                    "No es posible ingresar %(cost)s MXN en la tarea '%(task)s'.\n"
                    "La suma total de m² quedaría en %(total)s y supera los "
                    "%(max)s m² considerados en la orden de venta."
                ) % {
                    "cost": line.fs_m2_cost or 0.0,
                    "task": task.display_name,
                    "total": total_m2,
                    "max": task.fs_expected_m2,
                })