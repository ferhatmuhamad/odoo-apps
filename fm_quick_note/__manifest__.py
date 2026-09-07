{
    'name': 'Quick Notes',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Personal sticky notes with tags, priorities and deadlines',
    'description': """
Quick Notes
===========

A lightweight place to keep short personal reminders inside Odoo.

Every user gets a private notebook: notes you create are visible only to you,
while a Quick Notes Administrator can review all of them.

Features
--------
* Kanban, list and form views
* Tags with colours
* Three priority levels
* Optional deadline with automatic overdue highlighting
* Pin the notes that matter most
* Archive instead of delete

This module only depends on the Odoo base module, so it runs on both
Odoo Community and Odoo Enterprise.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad/odoo-apps',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/quick_note_security.xml',
        'security/ir.model.access.csv',
        'views/quick_note_views.xml',
        'views/quick_note_tag_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [
        'demo/quick_note_demo.xml',
    ],
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
