# -*- coding: utf-8 -*-
"""Everything the dashboard shows, computed here and nowhere else.

One request, one dict. The browser only draws. Every figure is in the
company's currency: an order in another currency is converted at the rate of
the period's last day, so a dashboard of a company that sells in three
currencies still adds up to one number.

Who sees what follows the Sales app's own groups: a salesperson with "Own
Documents Only" sees their orders, everyone above that sees the company's.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

STATES = [
    ('sale', 'Sales Order'),
    ('draft', 'Quotation'),
    ('sent', 'Quotation Sent'),
    ('cancel', 'Cancelled'),
]
QUOTATION_STATES = ('draft', 'sent')

INVOICE_STATUSES = [
    ('invoiced', 'Fully Invoiced'),
    ('to invoice', 'To Invoice'),
    ('no', 'Nothing to Invoice'),
    ('upselling', 'Upselling Opportunity'),
]

TOP_N = 10
RECENT_N = 15
PIPELINE_N = 8
TREND_MONTHS = 12


class SalesDashboard(models.AbstractModel):
    _name = 'fm.sales.dashboard'
    _description = 'Sales Dashboard'

    # ── Who sees what ────────────────────────────────────────────────────

    @api.model
    def _access(self):
        """('all' | 'own', domain). Mirrors the Sales app's own rules."""
        user = self.env.user
        if user._is_admin() or user.has_group('sales_team.group_sale_salesman_all_leads'):
            return 'all', []
        return 'own', [('user_id', '=', user.id)]

    # ── Periods ──────────────────────────────────────────────────────────

    @api.model
    def _period(self, date_from, date_to):
        today = fields.Date.context_today(self)
        date_from = fields.Date.from_string(date_from) if date_from else today.replace(day=1)
        date_to = fields.Date.from_string(date_to) if date_to else today
        if date_to < date_from:
            date_from, date_to = date_to, date_from
        return date_from, date_to

    @staticmethod
    def _date_domain(date_from, date_to, field='date_order'):
        return [
            (field, '>=', datetime.combine(date_from, datetime.min.time())),
            (field, '<=', datetime.combine(date_to, datetime.max.time())),
        ]

    # ── Money, in one currency ───────────────────────────────────────────

    def _convert(self, amount, currency, company, date):
        if not currency or currency == company.currency_id:
            return amount
        return currency._convert(amount, company.currency_id, company, date, round=False)

    def _sum(self, domain, company, date, model='sale.order', field='amount_total'):
        """Sum of a monetary field over a domain, converted per currency."""
        Model = self.env[model]
        total = 0.0
        for currency, amount in Model._read_group(domain, ['currency_id'], [field + ':sum']):
            total += self._convert(amount or 0.0, currency, company, date)
        return total

    def _sum_by(self, domain, company, date, groupby, model='sale.order', field='amount_total'):
        """{record: (amount, count)} for one grouping, converted per currency."""
        Model = self.env[model]
        out = defaultdict(lambda: [0.0, 0])
        for key, currency, amount, count in Model._read_group(
                domain, [groupby, 'currency_id'], [field + ':sum', '__count']):
            if not key:
                continue
            out[key][0] += self._convert(amount or 0.0, currency, company, date)
            out[key][1] += count
        return out

    # ── The whole dashboard ──────────────────────────────────────────────

    @api.model
    def get_data(self, date_from=None, date_to=None):
        company = self.env.company
        role, user_domain = self._access()
        date_from, date_to = self._period(date_from, date_to)
        base = [('company_id', '=', company.id)] + user_domain
        period = base + self._date_domain(date_from, date_to)
        currency = company.currency_id
        return {
            'summary': self._summary(period, company, date_to),
            'kpi': self._kpi(period, base, company, date_from, date_to),
            'by_state': self._by_state(period, company, date_to),
            'pipeline': self._pipeline(period, company, date_to),
            'top_customers': self._top_customers(period, company, date_to),
            'top_products': self._top_products(period, company, date_to),
            'teams': self._teams(period, company, date_to),
            'salespersons': self._salespersons(period, company, date_to),
            'monthly_trend': self._monthly_trend(base, company),
            'recent': self._recent(period),
            'invoice_status': self._invoice_status(period, company, date_to),
            'meta': {
                'company': company.name,
                'currency_symbol': currency.symbol or '',
                'currency_position': currency.position,
                'decimal_places': currency.decimal_places,
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'role': role,
                'user': self.env.user.name,
            },
        }

    def _summary(self, period, company, date):
        Order = self.env['sale.order']
        quotation = self._sum(period + [('state', 'in', QUOTATION_STATES)], company, date)
        quotation_n = Order.search_count(period + [('state', 'in', QUOTATION_STATES)])
        confirmed = self._sum(period + [('state', '=', 'sale')], company, date)
        confirmed_n = Order.search_count(period + [('state', '=', 'sale')])
        cancelled = self._sum(period + [('state', '=', 'cancel')], company, date)
        cancelled_n = Order.search_count(period + [('state', '=', 'cancel')])
        total_n = quotation_n + confirmed_n + cancelled_n
        return {
            'quotation_amount': quotation, 'quotation_count': quotation_n,
            'confirmed_amount': confirmed, 'confirmed_count': confirmed_n,
            'cancelled_amount': cancelled, 'cancelled_count': cancelled_n,
            'conversion_rate': (confirmed_n / total_n * 100.0) if total_n else 0.0,
            'avg_order_value': (confirmed / confirmed_n) if confirmed_n else 0.0,
            'total_sales': confirmed,
        }

    def _kpi(self, period, base, company, date_from, date_to):
        """The headline figures, with the previous period of the same
        length beside them so a number has something to be compared to."""
        Order = self.env['sale.order']
        revenue = self._sum(period + [('state', '=', 'sale')], company, date_to)
        confirmed_n = Order.search_count(period + [('state', '=', 'sale')])
        days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        prev = base + self._date_domain(prev_from, prev_to) + [('state', '=', 'sale')]
        prev_revenue = self._sum(prev, company, prev_to)
        prev_confirmed_n = Order.search_count(prev)
        customers = Order._read_group(period + [('state', '=', 'sale')], ['partner_id'], ['__count'])
        prev_customers = Order._read_group(prev, ['partner_id'], ['__count'])
        return {
            'total_orders': Order.search_count(period),
            'confirmed_orders': confirmed_n,
            'revenue': revenue,
            'avg_order_value': (revenue / confirmed_n) if confirmed_n else 0.0,
            'unique_customers': len(customers),
            'prev': {
                'revenue': prev_revenue,
                'confirmed_orders': prev_confirmed_n,
                'unique_customers': len(prev_customers),
                'avg_order_value': (prev_revenue / prev_confirmed_n) if prev_confirmed_n else 0.0,
                'date_from': fields.Date.to_string(prev_from),
                'date_to': fields.Date.to_string(prev_to),
            },
            'revenue_growth': ((revenue - prev_revenue) / prev_revenue * 100.0) if prev_revenue else None,
        }

    def _by_state(self, period, company, date):
        Order = self.env['sale.order']
        return [{
            'state': code, 'label': label,
            'count': Order.search_count(period + [('state', '=', code)]),
            'amount': self._sum(period + [('state', '=', code)], company, date),
        } for code, label in STATES]

    def _pipeline(self, period, company, date):
        Order = self.env['sale.order']
        out = []
        for code, label in STATES:
            domain = period + [('state', '=', code)]
            orders = Order.search(domain, order='date_order desc, id desc', limit=PIPELINE_N)
            out.append({
                'state': code, 'label': label,
                'count': Order.search_count(domain),
                'amount': self._sum(domain, company, date),
                'orders': [{
                    'id': o.id, 'name': o.name, 'partner': o.partner_id.name or '',
                    'amount': self._convert(o.amount_total, o.currency_id, company, date),
                    'date': fields.Date.to_string(o.date_order.date()) if o.date_order else '',
                    'user': o.user_id.name or '',
                } for o in orders],
            })
        return out

    def _top_customers(self, period, company, date):
        by = self._sum_by(period + [('state', '=', 'sale')], company, date, 'partner_id')
        rows = sorted(by.items(), key=lambda kv: kv[1][0], reverse=True)[:TOP_N]
        return [{'id': p.id, 'name': p.display_name, 'amount': a, 'order_count': n} for p, (a, n) in rows]

    def _top_products(self, period, company, date):
        # Order lines, so the amount is the product's own share of each order.
        domain = [('order_id.' + k if k in ('company_id', 'user_id', 'date_order') else k, op, v)
                  for k, op, v in period] + [('order_id.state', '=', 'sale'), ('display_type', '=', False)]
        Line = self.env['sale.order.line']
        out = defaultdict(lambda: [0.0, 0.0])
        for product, currency, amount, qty in Line._read_group(
                domain, ['product_id', 'currency_id'], ['price_subtotal:sum', 'product_uom_qty:sum']):
            if not product:
                continue
            out[product][0] += self._convert(amount or 0.0, currency, company, date)
            out[product][1] += qty or 0.0
        rows = sorted(out.items(), key=lambda kv: kv[1][0], reverse=True)[:TOP_N]
        return [{'id': p.id, 'name': p.display_name, 'amount': a, 'qty': q} for p, (a, q) in rows]

    def _teams(self, period, company, date):
        by = self._sum_by(period + [('state', '=', 'sale')], company, date, 'team_id')
        rows = sorted(by.items(), key=lambda kv: kv[1][0], reverse=True)
        return [{'id': t.id, 'name': t.name, 'amount': a, 'order_count': n} for t, (a, n) in rows]

    def _salespersons(self, period, company, date):
        by = self._sum_by(period + [('state', '=', 'sale')], company, date, 'user_id')
        rows = sorted(by.items(), key=lambda kv: kv[1][0], reverse=True)[:TOP_N]
        return [{'id': u.id, 'name': u.name, 'amount': a, 'order_count': n} for u, (a, n) in rows]

    def _monthly_trend(self, base, company):
        """The last twelve months, whatever the period filter says: a trend
        needs more than the month being looked at."""
        today = fields.Date.context_today(self)
        first = today.replace(day=1) - relativedelta(months=TREND_MONTHS - 1)
        last = today.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        domain = base + self._date_domain(first, last)
        buckets = {}
        for month, state, currency, amount in self.env['sale.order']._read_group(
                domain, ['date_order:month', 'state', 'currency_id'], ['amount_total:sum']):
            key = fields.Date.to_string(month)[:7] if month else None
            if not key:
                continue
            row = buckets.setdefault(key, {'quotation': 0.0, 'confirmed': 0.0, 'cancelled': 0.0})
            bucket = {'draft': 'quotation', 'sent': 'quotation', 'sale': 'confirmed', 'cancel': 'cancelled'}.get(state)
            if bucket:
                row[bucket] += self._convert(amount or 0.0, currency, company, last)
        out = []
        for i in range(TREND_MONTHS):
            month = first + relativedelta(months=i)
            key = month.strftime('%Y-%m')
            row = buckets.get(key, {'quotation': 0.0, 'confirmed': 0.0, 'cancelled': 0.0})
            out.append({'month': key, 'label': month.strftime('%b %Y'), **row})
        return out

    def _recent(self, period):
        state_labels = dict(STATES)
        invoice_labels = dict(INVOICE_STATUSES)
        orders = self.env['sale.order'].search(period, order='write_date desc, id desc', limit=RECENT_N)
        return [{
            'id': o.id, 'name': o.name, 'partner': o.partner_id.name or '',
            'amount': o.amount_total, 'currency_symbol': o.currency_id.symbol or '',
            'state': o.state, 'state_label': state_labels.get(o.state, o.state),
            'invoice_status': o.invoice_status,
            'invoice_label': invoice_labels.get(o.invoice_status, '') if o.state == 'sale' else '',
            'date': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, o.write_date))[:16]
                    if o.write_date else '',
            'user': o.user_id.name or '',
        } for o in orders]

    def _invoice_status(self, period, company, date):
        Order = self.env['sale.order']
        base = period + [('state', '=', 'sale')]
        return [{
            'status': code, 'label': label,
            'count': Order.search_count(base + [('invoice_status', '=', code)]),
            'amount': self._sum(base + [('invoice_status', '=', code)], company, date),
        } for code, label in INVOICE_STATUSES]

    # ── Click-through: every figure opens the records behind it ─────────

    @api.model
    def get_action(self, kind, date_from=None, date_to=None, res_id=None, state=None,
                   partner_id=None, product_id=None, team_id=None, user_id=None, invoice_status=None):
        company = self.env.company
        _role, user_domain = self._access()
        date_from, date_to = self._period(date_from, date_to)
        period = [('company_id', '=', company.id)] + user_domain + self._date_domain(date_from, date_to)

        if kind == 'order' and res_id:
            return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': res_id,
                    'views': [[False, 'form']], 'target': 'current'}

        if kind == 'product_lines' and product_id:
            domain = [('order_id.' + k if k in ('company_id', 'user_id', 'date_order') else k, op, v)
                      for k, op, v in period] + [('order_id.state', '=', 'sale'), ('product_id', '=', product_id)]
            product = self.env['product.product'].browse(product_id)
            return {'type': 'ir.actions.act_window', 'name': _('Sales of %s', product.display_name),
                    'res_model': 'sale.order.line', 'views': [[False, 'list'], [False, 'form']],
                    'domain': domain, 'context': {'create': 0}, 'target': 'current'}

        domain, name = list(period), _('Orders')
        if kind == 'state' and state:
            domain += [('state', '=', state)]
            name = dict(STATES).get(state, state)
        elif kind == 'quotations':
            domain += [('state', 'in', QUOTATION_STATES)]; name = _('Quotations')
        elif kind == 'confirmed':
            domain += [('state', '=', 'sale')]; name = _('Confirmed Orders')
        elif kind == 'cancelled':
            domain += [('state', '=', 'cancel')]; name = _('Cancelled Orders')
        elif kind == 'customer' and partner_id:
            domain += [('state', '=', 'sale'), ('partner_id', '=', partner_id)]
            name = _('Orders of %s', self.env['res.partner'].browse(partner_id).display_name)
        elif kind == 'team' and team_id:
            domain += [('state', '=', 'sale'), ('team_id', '=', team_id)]
            name = _('Orders of %s', self.env['crm.team'].browse(team_id).name)
        elif kind == 'salesperson' and user_id:
            domain += [('state', '=', 'sale'), ('user_id', '=', user_id)]
            name = _('Orders of %s', self.env['res.users'].browse(user_id).name)
        elif kind == 'invoice_status' and invoice_status:
            domain += [('state', '=', 'sale'), ('invoice_status', '=', invoice_status)]
            name = dict(INVOICE_STATUSES).get(invoice_status, invoice_status)
        elif kind == 'recent':
            name = _('Recent Orders')
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': 'sale.order',
                'views': [[False, 'list'], [False, 'form']], 'domain': domain,
                'context': {'create': 0}, 'target': 'current'}
