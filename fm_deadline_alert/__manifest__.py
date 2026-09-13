{
    'name': 'Deadline Alerts',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'A bell in the top bar for everything of yours that is due soon or overdue - activities and record deadlines - updated the moment it changes',
    'description': """
Deadline Alerts
===============

A bell in the top bar. It counts everything of yours that is overdue or
due within the next 24 hours, and lists it in three groups: overdue,
today, coming up. Click a line and the record opens; tick an activity and
it is done.

Two kinds of deadline, one bell
-------------------------------
* **Activities** assigned to you - the scheduled call, review, approval.
* **Record deadlines**: a task's deadline, a quotation's expiry, an
  invoice's due date, a lead's expected closing. Each is a *source*: a
  model, its deadline field, and the field that says whose record it is,
  plus which records still count (a done task has no deadline). Sources
  for Project, CRM, Sales, Purchase and Invoicing are added on install
  when those apps are present; any other model is a minute in Settings.

It keeps up
-----------
When an activity of yours is created, moved, done or deleted, your bell
learns about it at once through Odoo's bus - not on the next reload. A
notification pops only when the number of alerts has grown; never on
login. Record deadlines are re-read every few minutes and whenever the
bell is opened.

Settings
--------
The window (24 hours by default), whether new alerts pop a notification,
and whether Odoo's own activity badge should count planned activities as
well as today's and overdue ones.

Depends on nothing but Discuss. No new security group: the bell shows
each user what is theirs, and only what they may see.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['mail', 'bus', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/deadline_source_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_deadline_alert/static/src/scss/deadline.scss',
            'fm_deadline_alert/static/src/js/deadline_systray.js',
            'fm_deadline_alert/static/src/xml/deadline_systray.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'images': [
        'static/description/images/main_screenshot.png',
        'static/description/images/panel.png',
        'static/description/images/source_form.png',
        'static/description/images/settings.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
