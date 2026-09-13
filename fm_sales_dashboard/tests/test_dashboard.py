# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestSalesDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A company of its own: the figures below are exact, and a database
        # with demo data has this month's orders of its own.
        cls.company = cls.env['res.company'].create({'name': 'Dash Co'})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.currency = cls.company.currency_id
        cls.u_all = new_test_user(cls.env, login='sd_all', groups='sales_team.group_sale_salesman_all_leads',
                                  company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.u_own = new_test_user(cls.env, login='sd_own', groups='sales_team.group_sale_salesman',
                                  company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.team_a = cls.env['crm.team'].create({'name': 'Team A', 'company_id': cls.company.id})
        cls.team_b = cls.env['crm.team'].create({'name': 'Team B', 'company_id': cls.company.id})
        cls.p1 = cls.env['res.partner'].create({'name': 'Customer One'})
        cls.p2 = cls.env['res.partner'].create({'name': 'Customer Two'})
        cls.prod_a = cls.env['product.product'].create({'name': 'Widget A', 'list_price': 100.0})
        cls.prod_b = cls.env['product.product'].create({'name': 'Widget B', 'list_price': 10.0})
        cls.today = fields.Date.context_today(cls.env['fm.sales.dashboard'])
        cls.from_ = cls.today.replace(day=1)

    def _order(self, partner, user, team, lines, state='sale', days_ago=0, currency=None):
        order = self.env['sale.order'].with_company(self.company).create({
            'company_id': self.company.id,
            'partner_id': partner.id, 'user_id': user.id, 'team_id': team.id,
            'date_order': fields.Datetime.now() - timedelta(days=days_ago),
            'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': q, 'price_unit': u}) for p, q, u in lines],
            **({'currency_id': currency.id} if currency else {}),
        })
        if state == 'sale':
            order.action_confirm()
            # Confirming stamps date_order with "now"; the test wants its date.
            order.date_order = fields.Datetime.now() - timedelta(days=days_ago)
        elif state == 'cancel':
            order._action_cancel()
        elif state == 'sent':
            order.state = 'sent'
        return order

    def _data(self, user=None, **kw):
        return self.env['fm.sales.dashboard'].with_user(user or self.u_all).with_company(self.company).get_data(**kw)

    def test_summary_and_kpi(self):
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 2, 100)])            # 200 confirmed
        self._order(self.p2, self.u_own, self.team_b, [(self.prod_b, 5, 10)])             # 50 confirmed
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)], 'draft')   # 100 quotation
        self._order(self.p2, self.u_all, self.team_a, [(self.prod_b, 1, 10)], 'cancel')   # 10 cancelled
        d = self._data(date_from=str(self.from_), date_to=str(self.today))
        s, k = d['summary'], d['kpi']
        self.assertEqual(s['confirmed_count'], 2)
        self.assertAlmostEqual(s['confirmed_amount'], 250.0)
        self.assertEqual(s['quotation_count'], 1)
        self.assertAlmostEqual(s['quotation_amount'], 100.0)
        self.assertEqual(s['cancelled_count'], 1)
        self.assertAlmostEqual(s['conversion_rate'], 50.0)     # 2 of 4
        self.assertAlmostEqual(s['avg_order_value'], 125.0)
        self.assertEqual(k['total_orders'], 4)
        self.assertEqual(k['unique_customers'], 2)
        self.assertAlmostEqual(k['revenue'], 250.0)
        self.assertIsNone(k['revenue_growth'], 'no previous period, no growth figure')
        self.assertEqual(d['meta']['role'], 'all')

    def test_previous_period_growth(self):
        days = (self.today - self.from_).days + 1
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)], days_ago=days)   # previous period
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 3, 100)])                  # this period
        k = self._data(date_from=str(self.from_), date_to=str(self.today))['kpi']
        self.assertAlmostEqual(k['prev']['revenue'], 100.0)
        self.assertAlmostEqual(k['revenue'], 300.0)
        self.assertAlmostEqual(k['revenue_growth'], 200.0)

    def test_own_documents_only_sees_own(self):
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 2, 100)])
        self._order(self.p2, self.u_own, self.team_b, [(self.prod_b, 5, 10)])
        d = self._data(user=self.u_own, date_from=str(self.from_), date_to=str(self.today))
        self.assertEqual(d['meta']['role'], 'own')
        self.assertEqual(d['summary']['confirmed_count'], 1)
        self.assertAlmostEqual(d['summary']['confirmed_amount'], 50.0)
        self.assertEqual([c['name'] for c in d['top_customers']], ['Customer Two'])
        self.assertEqual([t['name'] for t in d['teams']], ['Team B'])

    def test_top_lists_and_teams(self):
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 2, 100), (self.prod_b, 4, 10)])
        self._order(self.p2, self.u_own, self.team_b, [(self.prod_b, 1, 10)])
        d = self._data(date_from=str(self.from_), date_to=str(self.today))
        self.assertEqual(d['top_customers'][0]['name'], 'Customer One')
        self.assertAlmostEqual(d['top_customers'][0]['amount'], 240.0)
        self.assertEqual(d['top_customers'][0]['order_count'], 1)
        self.assertEqual(d['top_products'][0]['name'], 'Widget A')
        self.assertAlmostEqual(d['top_products'][0]['amount'], 200.0)
        self.assertAlmostEqual(d['top_products'][1]['qty'], 5.0, msg='B: 4 + 1 units')
        self.assertEqual([t['name'] for t in d['teams']], ['Team A', 'Team B'])
        self.assertEqual(d['salespersons'][0]['name'], self.u_all.name)

    def test_by_state_pipeline_invoice(self):
        o = self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)])
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)], 'sent')
        d = self._data(date_from=str(self.from_), date_to=str(self.today))
        by = {r['state']: r for r in d['by_state']}
        self.assertEqual(by['sale']['count'], 1)
        self.assertEqual(by['sent']['count'], 1)
        self.assertEqual(by['draft']['count'], 0)
        pipe = {r['state']: r for r in d['pipeline']}
        self.assertEqual(pipe['sale']['orders'][0]['name'], o.name)
        inv = {r['status']: r for r in d['invoice_status']}
        self.assertEqual(inv['to invoice']['count'], 1, 'a confirmed order of a consumable is to invoice')

    def test_monthly_trend_has_twelve_months(self):
        self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)])
        trend = self._data()['monthly_trend']
        self.assertEqual(len(trend), 12)
        self.assertEqual(trend[-1]['month'], self.today.strftime('%Y-%m'))
        self.assertAlmostEqual(trend[-1]['confirmed'], 100.0)
        self.assertEqual(sum(r['confirmed'] for r in trend[:-1]), 0.0)

    def test_foreign_currency_is_converted(self):
        other = self.env['res.currency'].search([('id', '!=', self.currency.id), ('active', '=', True)], limit=1)
        if not other:
            other = self.env['res.currency'].create({'name': 'XTS', 'symbol': 'x'})
        self.env['res.currency.rate'].create({
            'currency_id': other.id, 'company_id': self.company.id,
            'name': self.from_, 'rate': 2.0})            # 2 units of `other` per 1 company unit
        pricelist = self.env['product.pricelist'].create({'name': 'Other', 'currency_id': other.id, 'company_id': self.company.id})
        order = self.env['sale.order'].with_company(self.company).create({
            'company_id': self.company.id,
            'partner_id': self.p1.id, 'user_id': self.u_all.id, 'pricelist_id': pricelist.id,
            'order_line': [(0, 0, {'product_id': self.prod_a.id, 'product_uom_qty': 1, 'price_unit': 200})],
        })
        order.action_confirm()
        self.assertEqual(order.currency_id, other)
        s = self._data(date_from=str(self.from_), date_to=str(self.today))['summary']
        self.assertAlmostEqual(s['confirmed_amount'], 100.0, places=1, msg='200 other = 100 company')

    def test_actions_are_filtered(self):
        o = self._order(self.p1, self.u_all, self.team_a, [(self.prod_a, 1, 100)])
        Dash = self.env['fm.sales.dashboard'].with_user(self.u_own).with_company(self.company)
        act = Dash.get_action('confirmed', date_from=str(self.from_), date_to=str(self.today))
        self.assertEqual(act['res_model'], 'sale.order')
        self.assertIn(('user_id', '=', self.u_own.id), act['domain'], 'own-documents scope follows the user')
        self.assertIn(('state', '=', 'sale'), act['domain'])
        act = Dash.get_action('order', res_id=o.id)
        self.assertEqual(act['res_id'], o.id)
        act = Dash.get_action('product_lines', product_id=self.prod_a.id,
                              date_from=str(self.from_), date_to=str(self.today))
        self.assertEqual(act['res_model'], 'sale.order.line')
        self.assertIn(('product_id', '=', self.prod_a.id), act['domain'])
        act = Dash.get_action('customer', partner_id=self.p1.id)
        self.assertIn('Customer One', act['name'])

    def test_period_defaults_and_swap(self):
        d = self._data(date_from='2030-01-31', date_to='2030-01-01')
        self.assertEqual(d['meta']['date_from'], '2030-01-01', 'reversed dates are swapped, not rejected')
        d = self._data()
        self.assertEqual(d['meta']['date_from'], str(self.from_))
        self.assertEqual(d['meta']['date_to'], str(self.today))
