from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

class SaleOrder(models.Model):
    _inherit = "sale.order"

    fs_link_google_maps = fields.Char(
        string="Enlace de Google Maps", 
        help="Enlace a la ubicación del cliente en Google Maps.",
    )   

    fs_direccion_instalacion = fields.Many2one(
        'res.partner',
        string="Dirección de instalación",
        domain=[('type', '=', 'instaltion')],
        help="Dirección específica para la instalación del servicio.",
    )

    fs_fecha_estimada_instalacion = fields.Datetime(
        string="Fecha estimada de instalación",
        tracking=True,
        help="Fecha y hora estimada para la instalación del servicio.",
    )
    
    commitment_date = fields.Datetime(tracking=True)

    def action_fs_open_availability(self):
        """Abre la vista de planeación de tareas FS en una ventana modal."""
        self.ensure_one()

        # OJO: reemplaza el XML ID de la acción por el de tu menú
        # "Planeación por usuario". Lo sacas desde Depurador > Editar acción.
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "industry_fsm.project_task_action_fsm_planning_groupby_user2"  # <-- cambia este xml_id si no coincide
        )

        # Mostrarla como popup y pasar info de la OV en el contexto
        action.update({
            "target": "new",  # ventana emergente
            "context": dict(self.env.context, active_id=self.id, active_model="sale.order"),
        })
        return action

    def _check_service_installation_address(self):
        """
        Verifica si hay servicios que requieren dirección de instalación.
        Returns: (bool, str) - (requiere_direccion, nombres_servicios)
        """
        self.ensure_one()
        
        # Mapeo de campos a nombres de servicio
        # Diccionario
        service_fields = {
            'fs_is_installation': 'instalación',
            'fs_is_leveling': 'nivelación',
            'fs_is_evaluation': 'evaluación',
        }

        found_services = []
        
        for line in self.order_line.filtered(lambda l: l.product_id):
            product = line.product_id.product_tmpl_id
            
            for field, name in service_fields.items():
                if getattr(product, field, False) and name not in found_services:
                    found_services.append(name)
        
        if not found_services:
            return False, ""
        
        # Formatear lista
        if len(found_services) == 1:
            services_text = found_services[0]
        else:
            services_text = ", ".join(found_services[:-1]) + f" y {found_services[-1]}"
        
        return True, services_text

    @api.constrains('fs_direccion_instalacion', 'order_line')
    def _check_shipping_address_for_installation(self):
        """Valida dirección de instalación para servicios."""
        for order in self:
            requires_address, services = order._check_service_installation_address()
            
            if requires_address and not order.fs_direccion_instalacion:
                raise ValidationError(_(
                    'Debe especificar una dirección de instalación cuando la orden '
                    'contiene servicios de %s.'
                ) % services)

    def action_confirm(self):
        """Validación al confirmar la orden."""
        for order in self:
            requires_address, services = order._check_service_installation_address()
            
            if requires_address and not order.fs_direccion_instalacion:
                raise ValidationError(_(
                    'No puede confirmar esta orden sin especificar una dirección de instalación.\n\n'
                    'La orden contiene servicios de %s que requieren una dirección de instalación.'
                ) % services)
        
        return super(SaleOrder, self).action_confirm()
