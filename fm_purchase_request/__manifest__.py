{
    'name': 'Purchase Request',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Staff ask in their own words; managers approve; purchasing orders in one click',
    'description': """
Purchase Request
================

A purchase request written from the requester's side of the desk.

The person who opens this most often is not a buyer. They do not know
product codes, they have no access to the Purchase app, and what they want
to know is simply "where is my request now". So here a request is a plain
list of things in the requester's own words, an approval by their own
manager, and a state that tells them what happened - all the way to "it
has arrived".

For the requester
-----------------
* An app of its own, **My Requests** - no Purchase access needed.
* Items are free text: *"HDMI cable, 2 m, for the meeting room"*, a
  quantity, an estimated price, a link. A product is optional.
* One line for what it is for; that is what the approver reads first.
* Every step lands in their inbox: approved, rejected (with the reason),
  ordered (with the order number), and the order confirmed with the vendor.
* The last word is theirs: **Received** is pressed by the person who asked.

For the manager
---------------
* Requests from their own people, found by Odoo's employee hierarchy -
  nothing to configure. An activity on submit, one button to approve.
* Reject asks for a reason. The requester reads it and can fix and resubmit.
* Above an amount you set, a purchase manager validates as well.

For purchasing
--------------
* Approved requests, from everyone, in the Purchase app where they work.
* **Create Purchase Order**, from one request or many at once: give each
  item a product and a vendor - or create a product from the item in one
  click for the one-off things - and the orders are made, one per vendor,
  or added to the vendor's open RFQ.
* Order lines keep the requester's words, and know which request item
  they fulfil. Quantities ordered and received flow back to the request.
* Smart buttons both ways: request to its orders, order to its requests.
* A printable request with the approval trail.

Built on Odoo's own Purchase, Employees and UoM. No new security groups:
the Purchase app's groups already say who buys and who manages.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['purchase', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'wizard/make_purchase_order_views.xml',
        'wizard/reject_views.xml',
        'views/purchase_request_views.xml',
        'views/purchase_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'report/purchase_request_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_purchase_request/static/src/scss/purchase_request.scss',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
