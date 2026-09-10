{
    'name': 'Team Drive for Employees',
    'version': '17.0.3.1.0',
    'category': 'Productivity/Documents',
    'summary': 'Per-employee document archives and department sharing for Team Drive',
    'description': """
Team Drive for Employees
========================

.. important::

   This is a free add-on for **Team Drive**, not a standalone app. It cannot
   be installed on its own - Odoo will refuse it unless Team Drive is
   installed first. Nothing extra to pay: if you own Team Drive, this is
   already yours.

Connects Team Drive to the Employees app. It installs itself automatically as
soon as both Team Drive and Employees are present, which is what lets Team
Drive itself stay free of any HR dependency and install on a database that
has no Employees app at all.

Per-employee archives
---------------------
Every employee gets an archive folder, built from folder templates that HR
edits from a menu rather than from code: Contracts, Diplomas, Certificates,
and whatever else the company keeps. New employees receive theirs on
creation; a nightly job backfills anyone created through a bulk import.

Who may look
------------
HR reads every archive, HR Managers maintain them, and an employee sees only
their own. A direct manager gets nothing by default - warning letters and
contracts are not their business. When there is a real need, HR shares the
document explicitly, and that sharing is recorded in the audit log.

Document lifetimes
------------------
A folder template can carry a default lifetime, so a file dropped into
"Contracts" is dated twelve months out without anyone typing a date. The
reminder then reaches the file owner, the employee, and HR Management.

Sharing with a whole department
-------------------------------
Adds "one department" as a sharing target next to "specific people". Child
departments inherit the permission, so sharing with Manufacturing reaches
the teams underneath it.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': [
        'fm_drive',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/fm_drive_hr_security.xml',
        'data/drive_template_data.xml',
        'data/ir_cron.xml',
        'views/drive_share_views.xml',
        'views/drive_template_views.xml',
        'views/hr_employee_views.xml',
        'views/menus.xml',
    ],
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'auto_install': True,
    'application': False,
    'installable': True,
}
