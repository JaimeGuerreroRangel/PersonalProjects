from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class ResUsers(models.Model):
    _inherit = "res.users"

    tariff_type = fields.Selection(
        [
            ("a", "Tarifa A"),
            ("b", "Tarifa B"),
        ],
        string="Tipo de tarifa",
        default="a",
        help="Define qué columna del tabulador se usa para calcular su costo.",
    )
    specialty_ids = fields.Many2many(
        "field.service.specialty",
        "res_users_fs_specialty_rel",
        "user_id",
        "specialty_id",
        string="Especialidades",
        help="Especialidades que este usuario puede atender.",
    )

    @api.model
    def _search(
        self,
        args,
        offset=0,
        limit=None,
        order=None,
        count=False,            # Odoo lo manda, lo aceptamos pero NO lo pasamos al super
        access_rights_uid=None, # Igual que count
        active_test=True,
        bypass_access=False,
    ):
        """
        Si en el contexto viene 'fs_task_specialty_id', filtramos los usuarios
        para que solo muestre los que tengan esa especialidad en specialty_ids.
        """
        specialty_id = self.env.context.get("fs_task_specialty_id")
        args_domain = fields.Domain(args or [])
        if specialty_id:
            args_domain &= fields.Domain("specialty_ids", "in", [specialty_id])

        # OJO: solo pasamos al super los argumentos que el core soporta.
        return super()._search(
            list(args_domain),
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )
