{
    'name': 'Attendance Correction',
    'version': '17.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Employees file their own missed check-in or check-out, the manager approves, HR validates, and only then does the attendance move',
    'description': """
Attendance Correction
=====================

Somebody forgets to clock in. Without this, the fix is a message to HR and
a hand-edited attendance: no record of who asked, who agreed, or why the
hours changed.

Here the employee files the correction themselves - the day, the time,
what happened, and a photo of the gate log if they have one. Their manager
approves it, HR validates it, and only then is the attendance written. The
whole trail stays attached to the record it changed.

* Missed check-in, missed check-out, or both.
* The form offers that employee's scheduled hours for the day, so most
  requests are two clicks.
* A missed check-out closes the attendance that is still open rather than
  creating a second one.
* A forgotten check-in with no check-out is closed at the end of that
  day's schedule - or left open if the day is still running, so the
  employee can clock out normally.
* Overlapping attendance is refused before anybody approves anything.
* How far back a correction may go is a setting; HR may always enter
  older ones directly.

Requires only Odoo Community modules.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'base_setup', 'mail'],
    'data': [
        'security/attendance_correction_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/attendance_correction_refuse_views.xml',
        'views/attendance_correction_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': [
        'static/description/images/main_screenshot.png',
        'static/description/images/form.png',
        'static/description/images/list.png',
        'static/description/images/settings.png',
        'static/description/images/employee.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
