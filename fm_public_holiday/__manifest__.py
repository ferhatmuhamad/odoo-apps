{
    'name': 'Public Holiday Importer',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Time Off',
    'summary': 'Import public holidays of 16 countries into your working schedules',
    'description': """
Public Holiday Importer
=======================

Odoo can exclude public holidays from working time, but you have to type every
single date yourself, every year, for every working schedule.

This module ships a reference list of public holidays and copies the ones you
pick into your working schedules in one step.

Features
--------
* 16 countries bundled, covering 2025 to 2030 - works with no extra install
* Pick a country, a year range and the working schedules to update
* Preview what will be imported before it is written
* Existing dates are detected and skipped, so importing twice is harmless
* Optional: install the `holidays` Python package to unlock every country it
  supports and any year range

Bundled countries
-----------------
Indonesia, Malaysia, Singapore, Philippines, Thailand, Vietnam, India,
United Arab Emirates, Belgium, France, Germany, Netherlands, Spain,
United States, Mexico, Brazil.

Note on Indonesia
-----------------
Only official national holidays are included. "Cuti bersama" (collective
leave) is announced each year by a joint ministerial decree and cannot be
generated in advance - add those dates manually.

This module depends on the Odoo base and Time Off apps only, so it runs on
both Odoo Community and Odoo Enterprise.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad/odoo-apps',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['hr_holidays'],
    'data': [
        'security/fm_public_holiday_security.xml',
        'security/ir.model.access.csv',
        'data/fm.public.holiday.csv',
        'views/fm_public_holiday_views.xml',
        'views/public_holiday_import_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
