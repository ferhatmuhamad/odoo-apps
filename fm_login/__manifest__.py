{
    'name': 'Modern Login',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Three login screens for Odoo, chosen by an administrator from Settings',
    'description': """
Modern Login
============

Three login screens for the same Odoo. An administrator picks one in
**Settings → Login Screen**, sees a preview of it there, and that is what
everyone gets.

The three
---------
* **Split** — a brand panel beside the form. The company gets half the screen.
* **Card** — one card on a plain ground. No panel, no imagery, no motion, for
  people who sign in several times a day and want the screen out of the way.
* **Open** — no card and no second column at all. The form stands directly on a
  field of colour, ranged left, with underlines instead of boxes. The colour is
  a setting: type a hex value and the whole screen follows it.

Safe by construction
--------------------
The login page is the one page in Odoo nobody can recover from through the
interface — break it and every account is locked out, administrator included.
Two things follow, and both are deliberate:

* Any setting this module does not recognise renders **Odoo's own login page**,
  reproduced unchanged. An empty value, a typo, or something left behind by an
  older version all land on a page that works.
* None of the three screens reimplements the form. Odoo injects it, so the
  fields, the CSRF token, the error messages, password reset and any OAuth
  buttons keep working exactly as they do without this module.

The background colour is validated as a plain six-digit hex before it is
stored, and whether text on it should be light or dark is worked out from the
colour's luminance — so a pale colour cannot produce a login page nobody can
read.

Nothing is written to any user record: both settings live in
``ir.config_parameter``. Uninstall and the standard Odoo login returns.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base_setup'],
    'data': [
        'views/login_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'fm_login/static/src/scss/login.scss',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
