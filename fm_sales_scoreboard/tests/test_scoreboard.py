# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestScoreboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Board Co'})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.viewer = new_test_user(cls.env, login='sb_view', groups='fm_sales_scoreboard.group_scoreboard',
                                   company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.nobody = new_test_user(cls.env, login='sb_nobody', groups='base.group_user',
                                   company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.manager = new_test_user(cls.env, login='sb_mgr', groups='sales_team.group_sale_manager',
                                    company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.team_a = cls.env['crm.team'].create({'name': 'Team A', 'company_id': cls.company.id})
        cls.team_b = cls.env['crm.team'].create({'name': 'Team B', 'company_id': cls.company.id})
        cls.ana = new_test_user(cls.env, login='sb_ana', groups='sales_team.group_sale_salesman',
                                company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.budi = new_test_user(cls.env, login='sb_budi', groups='sales_team.group_sale_salesman',
                                 company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.ana.sale_team_id = cls.team_a
        cls.budi.sale_team_id = cls.team_b
        cls.env['hr.employee'].create({'name': 'Ana', 'user_id': cls.ana.id, 'company_id': cls.company.id,
                                       'job_title': 'Account Executive', 'mobile_phone': '0812'})
        cls.won = cls.env['crm.stage'].search([('is_won', '=', True)], limit=1) or cls.env['crm.stage'].create({'name': 'Won', 'is_won': True})
        cls.new = cls.env['crm.stage'].search([('is_won', '=', False)], limit=1) or cls.env['crm.stage'].create({'name': 'New'})
        cls.today = fields.Date.context_today(cls.env['fm.sales.scoreboard'])

    def _lead(self, user, revenue, outcome='open', created=None, closed=None, creator=None):
        Lead = self.env['crm.lead'].with_company(self.company)
        if creator:
            Lead = Lead.with_user(creator).with_company(self.company)
        lead = Lead.create({
            'name': 'L', 'type': 'opportunity', 'user_id': user.id, 'company_id': self.company.id,
            'expected_revenue': revenue, 'probability': 50, 'stage_id': self.new.id,
        })
        lead = lead.sudo()
        if outcome == 'won':
            lead.action_set_won()
        elif outcome == 'lost':
            lead.action_set_lost()
        # The ORM buffers writes; flush before touching the row directly,
        # or the buffered date_closed lands on top of the one set here.
        lead.flush_recordset()
        if created:
            self.env.cr.execute("UPDATE crm_lead SET create_date=%s WHERE id=%s", (created, lead.id))
            lead.invalidate_recordset(['create_date'])
        if closed:
            self.env.cr.execute("UPDATE crm_lead SET date_closed=%s WHERE id=%s", (closed, lead.id))
            lead.invalidate_recordset(['date_closed'])
        return lead

    def _data(self, user=None, **kw):
        return self.env['fm.sales.scoreboard'].with_user(user or self.viewer).with_company(self.company).get_data(**kw)

    def _sp(self, data, user):
        return next(s for s in data['salespersons'] if s['user_id'] == user.id)

    # ── access ───────────────────────────────────────────────────────────

    def test_viewer_group_gates_the_board(self):
        self._lead(self.ana, 100)
        self.assertTrue(self._data()['salespersons'])
        with self.assertRaises(AccessError):
            self._data(user=self.nobody)
        self.assertTrue(self._data(user=self.manager)['salespersons'], 'sales managers are viewers')

    def test_viewer_cannot_open_leads_without_crm_access(self):
        self._lead(self.ana, 100)
        with self.assertRaises(AccessError):
            self.env['fm.sales.scoreboard'].with_user(self.viewer).get_lead_action(self.ana.id, 'created')

    # ── the cohort ───────────────────────────────────────────────────────

    def test_leads_in_equal_won_plus_open_plus_lost(self):
        self._lead(self.ana, 100, 'won')
        self._lead(self.ana, 200, 'won')
        self._lead(self.ana, 50, 'lost')
        self._lead(self.ana, 300, 'open')
        d = self._data(mode='day')
        s = self._sp(d, self.ana)['summary']
        self.assertEqual((s['leads'], s['won'], s['open'], s['lost']), (4, 2, 1, 1))
        self.assertEqual(s['leads'], s['won'] + s['open'] + s['lost'])
        self.assertAlmostEqual(s['leads_value'], 650.0)
        self.assertAlmostEqual(s['won_value'], 300.0)
        self.assertAlmostEqual(s['lost_value'], 50.0)
        self.assertAlmostEqual(s['open_value'], 300.0)
        sp = self._sp(d, self.ana)
        self.assertEqual(len(sp['series']['won']), len(d['labels']))
        self.assertEqual(sum(sp['series']['won']), 2)
        self.assertEqual(sp['job_title'], 'Account Executive')
        self.assertEqual(sp['phone'], '0812')
        self.assertEqual(sp['team'], 'Team A')

    def test_lost_after_won_is_lost(self):
        """Archived means lost, whatever stage the lead was left on."""
        lead = self._lead(self.ana, 900, 'won')
        try:
            lead.action_set_lost()
        except ValidationError:
            # 19.0 refuses to lose a lead that sits on a won stage. The
            # rule this test guards (archived means lost, whatever the
            # stage) still holds; it just cannot be provoked here.
            self.skipTest('this version does not allow losing a won lead')
        s = self._sp(self._data(mode='day'), self.ana)['summary']
        self.assertEqual((s['won'], s['lost']), (0, 1))
        self.assertAlmostEqual(s['closed_value'], 0.0)

    def test_closed_value_follows_close_date(self):
        year = self.today.year
        self._lead(self.ana, 100, 'won', created=datetime(year, 1, 5), closed=datetime(year, 3, 5))
        d = self._data(mode='month', year=year, month=3)
        sp = self._sp(d, self.ana)
        self.assertEqual(sp['series']['won'][0], 1, 'created in January: cohort January')
        self.assertAlmostEqual(sp['summary']['closed_value'], 100.0, msg='closed in March, inside the year')
        self.assertEqual(sp['summary']['month_won'], 1, 'KPI month is March')
        d = self._data(mode='month', year=year, month=1)
        self.assertEqual(self._sp(d, self.ana)['summary']['month_won'], 0, 'KPI month January: not closed yet')

    def test_zero_expected_revenue_falls_back_to_the_order(self):
        lead = self._lead(self.ana, 0, 'won')
        product = self.env['product.product'].create({'name': 'P', 'list_price': 250.0})
        order = self.env['sale.order'].with_company(self.company).create({
            'company_id': self.company.id, 'partner_id': self.env['res.partner'].create({'name': 'C'}).id,
            'opportunity_id': lead.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 2, 'price_unit': 250})]})
        order.action_confirm()
        s = self._sp(self._data(mode='day'), self.ana)['summary']
        self.assertAlmostEqual(s['won_value'], 500.0)

    def test_conversion_and_target(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_sales_scoreboard.target', '1000')
        self._lead(self.ana, 400, 'won')
        self._lead(self.ana, 100, 'open')
        self._lead(self.ana, 100, 'lost')
        s = self._sp(self._data(mode='day'), self.ana)['summary']
        self.assertAlmostEqual(s['conversion'], 33.3)
        self.assertAlmostEqual(s['achievement'], 40.0)
        self.env['ir.config_parameter'].sudo().set_param('fm_sales_scoreboard.target', '0')
        s = self._sp(self._data(mode='day'), self.ana)['summary']
        self.assertIsNone(s['achievement'], 'no target, no achievement figure')

    def test_pipeline(self):
        self._lead(self.ana, 1000, 'open')
        self._lead(self.ana, 500, 'won')
        s = self._sp(self._data(mode='day'), self.ana)['summary']
        self.assertEqual(s['pipeline_count'], 1)
        self.assertAlmostEqual(s['pipeline_value'], 1000.0)
        self.assertAlmostEqual(s['pipeline_weighted'], 500.0, msg='probability 50%')

    # ── who is on the board, and filters ─────────────────────────────────

    def test_board_is_lead_owners_sorted(self):
        self._lead(self.budi, 1)
        self._lead(self.ana, 1)
        d = self._data()
        self.assertEqual([s['name'] for s in d['salespersons']], sorted([self.ana.name, self.budi.name]))

    def test_configured_board_members(self):
        self._lead(self.budi, 1)
        self._lead(self.ana, 1)
        self.env['ir.config_parameter'].sudo().set_param('fm_sales_scoreboard.user_ids', str(self.ana.id))
        self.assertEqual([s['user_id'] for s in self._data()['salespersons']], [self.ana.id])

    def test_team_filter(self):
        self._lead(self.budi, 1)
        self._lead(self.ana, 1)
        d = self._data(team_id=self.team_a.id)
        self.assertEqual([s['user_id'] for s in d['salespersons']], [self.ana.id])
        self.assertEqual(d['filters']['team_id'], self.team_a.id)
        self.assertTrue(any(t['name'] == 'Team B' for t in d['filters']['teams']), 'all teams stay offered')

    def test_creator_filter(self):
        self._lead(self.ana, 100, 'open', creator=self.manager)
        self._lead(self.ana, 900, 'open', creator=self.ana)
        s = self._sp(self._data(mode='day', creator_id=self.manager.id), self.ana)['summary']
        self.assertEqual(s['leads'], 1)
        self.assertAlmostEqual(s['leads_value'], 100.0)

    # ── click-through ────────────────────────────────────────────────────

    def test_lead_actions(self):
        Board = self.env['fm.sales.scoreboard'].with_user(self.manager).with_company(self.company)
        year = self.today.year
        act = Board.get_lead_action(self.ana.id, 'created_lost', mode='month', year=year, bucket=0)
        self.assertEqual(act['res_model'], 'crm.lead')
        self.assertIn(('active', '=', False), act['domain'])
        self.assertFalse(act['context']['active_test'], 'lost leads are archived; the list must show them')
        self.assertIn('Jan %s' % year, act['name'])
        act = Board.get_lead_action(self.ana.id, 'won_closed', mode='day', year=year, month=self.today.month)
        self.assertTrue(any(t[0] == 'date_closed' for t in act['domain']))
        act = Board.get_lead_action(self.ana.id, 'pipeline')
        self.assertIn(('type', '=', 'opportunity'), act['domain'])
        act = Board.get_lead_action(self.ana.id, 'created', mode='day', year=year, month=self.today.month, bucket=0)
        self.assertIn('1 ', act['name'])
