from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class FsmTaskImage(models.Model):
    _name = 'fsm.task.image'
    _description = 'Imágenes de la tarea de Field Service'
    _order = 'sequence, id'

    task_id = fields.Many2one(
        'project.task',
        string='Tarea',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string='Descripción')
    sequence = fields.Integer(string='Secuencia', default=10)

    # Puedes usar Image en lugar de Binary para que Odoo maneje thumbnails
    image = fields.Binary(
        string='Imagen',
        # max_width=1024,
        # max_height=1024,
        required=True,
        attachment=True,
    )

class ProjectTask(models.Model):
    _inherit = 'project.task'

    fsm_image_ids = fields.One2many(
        'fsm.task.image',
        'task_id',
        string='Imágenes del trabajo',
    )

    @api.constrains('fsm_image_ids')
    def _check_fsm_images_max(self):
        """Validar máximo de 4 imágenes siempre"""
        for task in self:
            total = len(task.fsm_image_ids)
            if total > 4:
                raise ValidationError(
                    _("La tarea %s tiene %s imágenes. "
                      "El máximo permitido es 4.") %
                    (task.display_name, total)
                )
