{
    'name': 'Custom CN Sync',
    'summary': 'China warehouse sync queue, snapshots and retry workflow',
    'description': """
Provides a resilient queue layer for syncing outbound operations and
maintaining China warehouse inventory snapshots.
    """,
    'author': 'Lainey Team',
    'website': 'https://example.com',
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'custom_wms_base',
        'stock',
        'sale_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/default_config.xml',
        'data/ir_cron.xml',
        'views/cn_sync_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}
