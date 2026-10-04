{
    'name': 'Hide Menus and Apps per User',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Hide whole apps or single menu entries for particular users - one at a time, or for a whole group at once',
    'description': """
Hide Menus and Apps per User
============================

Odoo shows everybody every app their access rights allow. For most people
that is more than they will ever open: a warehouse operator does not need
Calendar, Discuss and Contacts in their way.

This adds two lists on a user:

* **Hidden apps** - whole applications, gone from the app row and from
  everywhere else. Calendar, Discuss, Contacts, whatever you choose.
* **Hidden menus** - single entries inside an app they otherwise use.

Both hide everything underneath them, and both take effect on that
person's next page load. Nobody else's menu changes.

How to use it
-------------
One person: Settings > Users & Companies > Users > the person > the **Menu**
tab > fill in *Hidden apps* and/or *Hidden menus* > Save. They see the new
menu on their next page load. *Show everything again* clears both lists.

A whole group: Settings > Users & Companies > **Hide Menus**. Pick a group
and the user list fills itself, choose the apps and menus, then *Hide
these*, *Show these again*, or *Make this the whole list* - the last one is
for making a department's menus identical.

**This hides; it does not forbid.** Somebody who knows the address can
still open what is hidden, exactly as before. Taking access away is what
access rights are for; this is for tidying a screen that has grown too
busy. One exception the module makes for you: an administrator always
keeps Settings, so a mistake can always be undone.

Requires only Odoo Community modules.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'wizard/hide_menu_wizard_views.xml',
    ],
    'images': [
        'static/description/images/main_screenshot.png',
        'static/description/images/apps.png',
        'static/description/images/user.png',
        'static/description/images/wizard.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
