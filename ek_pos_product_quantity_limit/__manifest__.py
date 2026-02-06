# -*- coding: utf-8 -*-
{
    'name': "POS Product Quantity Limit",
    'version': '18.0',
    'summary': """Product Quantity Limit in Point of Sale and invoice""",
    "category": 'Warehouse,Point of Sale',
    'description': """Module adds functionality to Limit Product Quantity in Point of Sale and invoice.""",
    'company': "eK Solutions",
    'author': "eK Solutions",
    'website': "https://ek-solutions.odoo.com",
    'live_test_url': '',
    'price': 0,
    'currency': 'USD',
    'depends': ['stock', 'point_of_sale','sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/product_product_views.xml',
    ],
    'assets': {
        'web.assets_backend': [

        ],
        'point_of_sale._assets_pos': [
            '/ek_pos_product_quantity_limit/static/src/xml/RestrictQuantityPopup.xml',
            '/ek_pos_product_quantity_limit/static/src/js/RestrictQuantityPopup.js',
            '/ek_pos_product_quantity_limit/static/src/js/product_screen.js',
            '/ek_pos_product_quantity_limit/static/src/js/pos_store.js',
            '/ek_pos_product_quantity_limit/static/src/js/order_summary.js',
        ],
    },
    'images': ['static/description/banner.gif'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
