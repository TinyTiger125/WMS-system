{
    'name': 'Custom Customs Export',
    'summary': 'Generate CN customs declaration Excel from done outbound transfers',
    'description': """
Provides a wizard to export customs declaration worksheets from completed
outbound pickings, using product customs metadata.
    """,
    'author': 'Lainey Team',
    'website': 'https://example.com',
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'custom_wms_base',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/customs_export_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
}
