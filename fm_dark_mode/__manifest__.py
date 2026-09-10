{
    'name': 'Modern Dark Mode',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'A dark theme for the Odoo backend, with a light / dark / system toggle',
    'description': """
Modern Dark Mode
================

A dark theme for the whole Odoo backend, on Community and Enterprise
alike. Three states, not two: **Light**, **Dark**, and **System**, which
follows whatever the operating system is set to and changes with it.

Covers the parts that usually stay white
----------------------------------------
Most dark themes recolour the screens their author happened to be
looking at, and everything else keeps its white background. This one
also styles the *structural* layer that every module is built on:

* ``.o-overlay-container`` — where Odoo puts notifications, dialogs,
  popovers and tooltips. These are the first things to give a dark
  theme away, and the easiest to forget.
* Bootstrap components — cards, tables, forms, dropdowns, tabs,
  off-canvas panels — so a module written after this theme still lands
  on sensible colours instead of white.
* ``color-scheme: dark``, so the browser's own widgets follow too:
  scrollbars, date pickers, and the list a ``<select>`` opens, none of
  which any stylesheet can reach inside.

Follows the system even in a background tab
--------------------------------------------
Browsers throttle background tabs, and the media-query event that
announces "the OS just went dark" can go undelivered. Leave Odoo open
through the afternoon and it would still be in the light theme at
night until you reloaded. The theme is re-checked whenever the tab
becomes visible again, so that no longer happens.

Where the toggle lives
----------------------
Install **Modern Home Grid** as well and a theme button appears beside
its search box. Without this module that button is not there at all —
neither module depends on the other; the home grid simply asks whether
a theme service is present.

The choice is stored per browser in ``localStorage`` under
``fm_hg_theme``, so nothing is written to your database.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            # Order matters. The hand-tuned Odoo rules load first; the
            # structural coverage loads after so it only fills the gaps
            # they leave, rather than overriding them.
            'fm_dark_mode/static/src/scss/dark_mode.scss',
            'fm_dark_mode/static/src/scss/dark_mode_coverage.scss',
            'fm_dark_mode/static/src/js/dark_mode_service.js',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
