from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = "res.company"

    fs_coordinator_installation_id = fields.Many2one(
        "res.users",
        string="Coordinador colocación",
        store=True,
    )
    fs_coordinator_leveling_id = fields.Many2one(
        "res.users",
        string="Coordinador nivelación",
        store=True,
    )
    fs_coordinator_evaluator_id = fields.Many2one(
        "res.users",
        string="Coordinador evaluación",
        store=True,
    )
    
    # CAMPOS MANY2MANY
    fs_coordinator_installation_ids = fields.Many2many(
        "res.users",
        "company_fs_coordinator_installation_rel",
        "company_id",
        "user_id",
        string="Coordinadores colocación",
        store=True,
    )
    fs_coordinator_leveling_ids = fields.Many2many(
        "res.users",
        "company_fs_coordinator_leveling_rel",
        "company_id",
        "user_id",
        string="Coordinadores nivelación",
        store=True,
    )
    fs_coordinator_evaluator_ids = fields.Many2many(
        "res.users",
        "company_fs_coordinator_evaluator_rel",
        "company_id",
        "user_id",
        string="Coordinadores evaluación",
        store=True,
    )

    fs_commission_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de comisiones FS",
        domain=[("type", "=", "purchase")],
        help="Diario donde se generarán las facturas de proveedor por comisiones.",
    )
    fs_commission_product_id = fields.Many2one(
        "product.product",
        string="Producto comisión FS",
        help="Producto que se usará en la línea de la factura de proveedor (Comisión).",
    )

    fs_arrival_tolerance_minutes = fields.Integer(
        string="Tolerancia de llegada (minutos)",
        default=10,
        help="Minutos de tolerancia para considerar que el técnico llegó 'a tiempo'. "
        "Se usa para calcular el KPI de llegadas en Field Service.",
    )

    fs_installation_policy = fields.Text(
        string="Políticas de colocación",
        help="Leyenda que se imprime en las hojas de trabajo / remisiones.",
    )

    fs_travel_approval_category_id = fields.Many2one(
        "approval.category",
        string="Categoría aprobación viáticos (FS)",
        help="Categoría de Aprobaciones que se usará al crear solicitudes de viáticos desde tareas de Field Service.",
    )
