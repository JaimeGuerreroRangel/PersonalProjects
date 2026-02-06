from odoo import models, api
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def create(self, vals):
        sale_order = self.env['sale.order'].browse(vals.get('order_id'))

        product_order_limit = self.env['ir.config_parameter'].sudo().get_param(
            'ek_pos_product_quantity_limit.is_pos_bill_quantity_limit')
        
        product_quantity_limit = self.env['ir.config_parameter'].sudo().get_param(
            'ek_pos_product_quantity_limit.is_pos_bill_quantity_limit')

        if product_order_limit:
            pos_bill_quantity_limit_type = self.env['ir.config_parameter'].sudo().get_param(
                'ek_pos_product_quantity_limit.pos_bill_quantity_limit_type')
            if pos_bill_quantity_limit_type == "both":
                product_quantity_limit_type = self.env['ir.config_parameter'].sudo().get_param(
                    'ek_pos_product_quantity_limit.pos_bill_quantity_limit')
                product_quantity_limit_type = int(product_quantity_limit_type)
                order_line_count = len(sale_order.order_line)
                if product_quantity_limit_type <= order_line_count:
                    raise ValidationError(f"Cannot add more than {product_quantity_limit_type} order lines to Sales Order {sale_order.name}.")
        
        if product_quantity_limit:
            product_quantity_limit_type = self.env['ir.config_parameter'].sudo().get_param(
                'ek_pos_product_quantity_limit.product_quantity_limit_type')
            if product_quantity_limit_type == 'both':
                existing_order_lines = sale_order.order_line.filtered(lambda line: line.product_id.id == vals.get('product_id'))
                total_existing_quantity = 0
                if existing_order_lines:
                    total_existing_quantity = sum(existing_order_lines.mapped('product_uom_qty'))
                product = self.env['product.product'].browse(vals.get('product_id'))
                max_quantity_limit = product.limit_quantity if product.limit_quantity else 0
                product_uom_qty = vals.get('product_uom_qty')
                if max_quantity_limit > 0 and max_quantity_limit < (product_uom_qty + total_existing_quantity):
                    raise ValidationError(f"Cannot add more than {max_quantity_limit} quantity for product {product.name}.")
        
        # Call the super method to create the order line
        return super(SaleOrderLine, self).create(vals)

    def write(self, vals):
        for line in self:
            sale_order = line.order_id

            product_quantity_limit = self.env['ir.config_parameter'].sudo().get_param(
                'ek_pos_product_quantity_limit.is_pos_bill_quantity_limit')

            if product_quantity_limit:
                product_quantity_limit_type = self.env['ir.config_parameter'].sudo().get_param(
                    'ek_pos_product_quantity_limit.product_quantity_limit_type')
                if product_quantity_limit_type == 'both':
                    # Retrieve the product for the current line
                    product = line.product_id

                    # Get the total quantity of existing order lines for this product
                    existing_order_lines = sale_order.order_line.filtered(lambda l: l.product_id.id == product.id)
                    total_existing_quantity = sum(existing_order_lines.mapped('product_uom_qty')) if existing_order_lines else 0

                    if vals.get('product_uom_qty'):
                    # Get the new quantity being set from vals
                        new_product_uom_qty = vals.get('product_uom_qty')

                        # Determine the max quantity limit
                        max_quantity_limit = product.limit_quantity if product.limit_quantity else 0
                        if new_product_uom_qty:
                            # Validation check
                            if max_quantity_limit > 0 and max_quantity_limit < (new_product_uom_qty + total_existing_quantity - line.product_uom_qty):
                                raise ValidationError(f"Cannot add more than {max_quantity_limit} quantity for product {product.name}.")

        # Call the super method to write the order line
        return super(SaleOrderLine, self).write(vals)

