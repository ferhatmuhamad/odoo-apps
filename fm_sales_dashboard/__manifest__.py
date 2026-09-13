{
    'name': 'Sales Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'One page for the state of sales: revenue against last period, trend, status, top customers and products, teams, invoicing',
    'description': """
Sales Dashboard
===============

One page that answers "how are sales going" - opened in the morning, read in
a minute, and every figure on it opens the orders behind it.

What is on it
-------------
* **Headline figures** for the period, each beside the same figure for the
  previous period of the same length: revenue, confirmed orders, quotations,
  cancellations, average order value, customers who bought.
* **Monthly trend** over the last twelve months - confirmed, quotations and
  cancelled, on one axis.
* **Orders by status** and **invoicing status**, each as a ring with the counts
  and amounts beside it.
* **Top customers** and **top products**, ranked, with the share drawn inline.
* **Sales teams** and **salespersons** as ranked bars.
* **Pipeline**: the latest orders in each status, in four columns.
* **Recent activity**: the last orders touched, with status and invoicing.

Every number is a link. Click a customer, a product, a team, a status, a bar
or a row and the matching list of orders opens, already filtered to the
period.

Periods
-------
This month, last month, this quarter, this year, or any two dates. Figures
follow the order date. Amounts are in the company's currency: orders in
another currency are converted, so a company that sells in three currencies
still gets one number.

Who sees what
-------------
The Sales app's own groups: a salesperson with "Own Documents Only" sees
their own orders; everyone above sees the company's.

Built with Odoo's own Chart.js bundle - nothing fetched from the internet,
nothing vendored - and drawn in colours that follow the backend's theme,
light or dark.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_sales_dashboard/static/src/scss/dashboard.scss',
            'fm_sales_dashboard/static/src/js/dashboard.js',
            'fm_sales_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
