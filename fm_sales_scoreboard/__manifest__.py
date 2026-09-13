{
    'name': 'Sales Scoreboard',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'A board for the wall: one salesperson at a time, won / in progress / lost, conversion and target, then the ranking - auto-sliding, auto-refreshing',
    'description': """
Sales Scoreboard
================

A board for the screen on the sales-room wall. It shows one salesperson at
a time - photo, name, team - with their leads for the year or the month
split into **won, in progress and lost**, their conversion rate and target
achievement for the month, their open pipeline, and then slides to the
next. The last slide is the **ranking** of everyone by closed value. Then
it starts again. The figures refresh on their own.

What it shows
-------------
* **Leads in, by outcome**: every lead that came in, by the month it came
  in (yearly view) or the day (monthly view), stacked as won / in progress
  / lost. One query, so *leads in = won + in progress + lost*, always.
* **Two units**: value (expected revenue, or the confirmed order's total
  when the expectation was left at zero) or count.
* **Closed value** for the period, by the date the deal closed - the money
  that became real.
* **Conversion rate** and **target achievement** for the month, with a
  target line on the chart when a monthly target is set.
* **Open pipeline**: opportunities, value, weighted by probability.
* **Ranking**: everyone, by closed value, with deals, conversion and target.

Every figure and every bar opens the leads behind it in CRM.

Filters: year, month, yearly / monthly view, value / count, sales team,
and who created the lead. Keyboard: arrows to move, space to pause,
f for fullscreen.

Settings (CRM): slide and refresh intervals, monthly target per
salesperson, which stages count as won, who is on the board, and which
users the "created by" filter offers.

Access: a group of its own, *Sales Scoreboard / Viewer*, meant for the
user the television logs in as. Sales managers have it. The board reads
CRM with elevated rights so that user needs nothing else; opening a list
from it needs real CRM access.

Built for a television: one theme, dark, large numerals, and outcome
colours validated for colour-vision deficiency. Charts are Odoo's own
Chart.js bundle - nothing from the internet.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['crm', 'sale_crm', 'hr'],
    'data': [
        'security/security.xml',
        'views/scoreboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_sales_scoreboard/static/src/scss/scoreboard.scss',
            'fm_sales_scoreboard/static/src/js/scoreboard.js',
            'fm_sales_scoreboard/static/src/xml/scoreboard.xml',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
