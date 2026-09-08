{
    'name': 'Modern Home Grid',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Full-page app launcher with instant search for Odoo Community',
    'description': """
Modern Home Grid
================

Odoo Community lists your apps in a small dropdown. This module replaces it
with a full-page launcher: every app as a large icon, and a search box that
filters apps and their menu items as you type.

Features
--------
* Full-page app grid, centred, with a soft designed background
* Instant search across apps and their menu items
* Full keyboard control: type to filter, arrow keys to move, Enter to open,
  Escape to close
* No configuration, no data model, no server load - pure interface
* Works on desktop, tablet and mobile
* Follows the light and dark themes of your Odoo

Requires only the Odoo `web` module, so it runs on any Odoo installation.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'fm_home_grid/static/src/scss/home_grid.scss',
            'fm_home_grid/static/src/scss/navbar.scss',
            'fm_home_grid/static/src/js/home_grid.js',
            'fm_home_grid/static/src/js/navbar_patch.js',
            'fm_home_grid/static/src/js/webclient_patch.js',
            'fm_home_grid/static/src/xml/home_grid.xml',
            'fm_home_grid/static/src/xml/navbar.xml',
            'fm_home_grid/static/src/xml/webclient.xml',
        ],
        'web.assets_tests': [
            'fm_home_grid/static/tests/tours/**/*',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
