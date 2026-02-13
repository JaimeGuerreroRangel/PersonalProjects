# -*- coding: utf-8 -*-
from odoo import models

class AccountMove(models.Model):
    _inherit = "account.move"

    def _fs_clear_commission_links_on_analytic_lines(self):
        """Limpia la comisión FS en las líneas analíticas ligadas a estas facturas."""
        AnalyticLine = self.env["account.analytic.line"].sudo()
        lines = AnalyticLine.search([("fs_commission_move_id", "in", self.ids)])
        if lines:
            lines.write({
                "fs_commission_paid": False,
                "fs_commission_move_id": False,
            })

    def write(self, vals):
        res = super().write(vals)

        # Si el estado quedó en cancelado, limpiar comisión FS.
        # (Cubre button_cancel y cualquier otra escritura que cancele.)
        if "state" in vals:
            cancelled_moves = self.filtered(lambda m: m.state == "cancel")
            if cancelled_moves:
                cancelled_moves._fs_clear_commission_links_on_analytic_lines()

        return res

    def unlink(self):
        # Antes de borrar, limpia comisión FS en analíticas ligadas.
        self._fs_clear_commission_links_on_analytic_lines()
        return super().unlink()
