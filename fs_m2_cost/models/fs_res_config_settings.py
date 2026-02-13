from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    
    # CAMPOS ORIGINAL

    fs_coordinator_installation_id = fields.Many2one(
        "res.users",
        string="Coordinador colocación",
        related="company_id.fs_coordinator_installation_id",
        readonly=False,
    )

    fs_coordinator_leveling_id = fields.Many2one(
        "res.users",
        string="Coordinador nivelación",
        related="company_id.fs_coordinator_leveling_id",
        readonly=False,
    )

    fs_coordinator_evaluator_id = fields.Many2one(
        "res.users",
        string="Coordinador evaluación",
        related="company_id.fs_coordinator_evaluator_id",
        readonly=False,
    )
    
    # CAMPOS MANY2MANY
    fs_coordinator_installation_ids = fields.Many2many(
        "res.users",
        string="Coordinadores colocación",
        related="company_id.fs_coordinator_installation_ids",
        readonly=False,
    )
    fs_coordinator_leveling_ids = fields.Many2many(
        "res.users",
        string="Coordinadores nivelación",
        related="company_id.fs_coordinator_leveling_ids",
        readonly=False,
    )
    fs_coordinator_evaluator_ids = fields.Many2many(
        "res.users",
        string="Coordinadores evaluación",
        related="company_id.fs_coordinator_evaluator_ids",
        readonly=False,
    )

    fs_commission_journal_id = fields.Many2one(
        related="company_id.fs_commission_journal_id",
        readonly=False,
        string="Diario de comisiones FS",
    )
    fs_commission_product_id = fields.Many2one(
        related="company_id.fs_commission_product_id",
        readonly=False,
        string="Producto comisión FS",
    )

    fs_arrival_tolerance_minutes = fields.Integer(
        related="company_id.fs_arrival_tolerance_minutes",
        string="Tolerancia de llegada (minutos)",
        readonly=False,
        help="Minutos de tolerancia para considerar que el técnico llegó 'a tiempo'.",
    )

    fs_installation_policy = fields.Text(
        related="company_id.fs_installation_policy",
        readonly=False,
        string="Políticas de colocación",
    )

    fs_travel_approval_category_id = fields.Many2one(
        "approval.category",
        string="Categoría aprobación viáticos (FS)",
        related="company_id.fs_travel_approval_category_id",
        readonly=False,
    )
