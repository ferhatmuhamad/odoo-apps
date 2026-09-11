# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestPurchaseRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Three people: a requester with no purchase rights, their manager
        # (also no purchase rights), and a buyer. Plus a purchase manager.
        cls.u_req = new_test_user(cls.env, login='pr_req', groups='base.group_user')
        cls.u_mgr = new_test_user(cls.env, login='pr_mgr', groups='base.group_user')
        cls.u_buy = new_test_user(cls.env, login='pr_buy', groups='base.group_user,purchase.group_purchase_user')
        cls.u_pm = new_test_user(cls.env, login='pr_pm', groups='base.group_user,purchase.group_purchase_manager')
        cls.u_other = new_test_user(cls.env, login='pr_other', groups='base.group_user')
        cls.dept = cls.env['hr.department'].create({'name': 'Marketing'})
        cls.e_mgr = cls.env['hr.employee'].create({'name': 'Mgr', 'user_id': cls.u_mgr.id})
        cls.e_req = cls.env['hr.employee'].create({
            'name': 'Req', 'user_id': cls.u_req.id, 'parent_id': cls.e_mgr.id,
            'department_id': cls.dept.id})
        cls.e_other = cls.env['hr.employee'].create({'name': 'Other', 'user_id': cls.u_other.id})
        cls.vendor_a = cls.env['res.partner'].create({'name': 'Vendor A', 'is_company': True})
        cls.vendor_b = cls.env['res.partner'].create({'name': 'Vendor B', 'is_company': True})
        cls.product = cls.env['product.product'].create({
            'name': 'HDMI cable', 'purchase_ok': True, 'standard_price': 50.0})
        cls.unit = cls.env.ref('uom.product_uom_unit')

    def _request(self, user=None, lines=None, purpose='Meeting room refresh'):
        Request = self.env['fm.purchase.request'].with_user(user or self.u_req)
        if lines is None:
            lines = [
                {'name': 'HDMI cable 2 m', 'product_qty': 2, 'price_estimated': 60.0},
                {'name': 'Whiteboard markers, box', 'product_qty': 3, 'price_estimated': 25.0},
            ]
        return Request.create({
            'purpose': purpose,
            'line_ids': [(0, 0, l) for l in lines],
        })

    def _wizard(self, requests, user=None, **line_updates):
        Wiz = self.env['fm.purchase.request.make.po'].with_user(user or self.u_buy)
        wiz = Wiz.with_context(active_model='fm.purchase.request', active_ids=requests.ids).create({})
        for line in wiz.line_ids:
            line.write(dict(line_updates))
        return wiz

    # ── the requester's side ─────────────────────────────────────────────

    def test_defaults_come_from_the_employee(self):
        req = self._request()
        self.assertEqual(req.requester_id, self.e_req)
        self.assertEqual(req.user_id, self.u_req)
        self.assertEqual(req.manager_id, self.e_mgr)
        self.assertEqual(req.approver_user_id, self.u_mgr)
        self.assertEqual(req.department_id, self.dept)
        self.assertTrue(req.name.startswith('PR/'))
        self.assertEqual(req.amount_estimated, 2 * 60 + 3 * 25)
        self.assertIn(self.u_req.partner_id, req.message_partner_ids)

    def test_submit_needs_items(self):
        req = self._request(lines=[])
        with self.assertRaises(UserError):
            req.action_submit()

    def test_submit_schedules_the_manager(self):
        req = self._request()
        req.action_submit()
        self.assertEqual(req.state, 'submitted')
        self.assertTrue(req.date_submitted)
        act = req.activity_ids
        self.assertEqual(len(act), 1)
        self.assertEqual(act.user_id, self.u_mgr)

    def test_no_manager_goes_to_purchase_manager(self):
        req = self._request(user=self.u_other)
        self.assertFalse(req.manager_id)
        req.action_submit()
        self.assertEqual(req.state, 'to_validate')

    def test_requester_cannot_approve_own(self):
        req = self._request()
        req.action_submit()
        self.assertFalse(req.can_approve)
        with self.assertRaises(AccessError):
            req.action_approve()

    def test_requester_sees_only_own(self):
        mine = self._request()
        theirs = self._request(user=self.u_other)
        Request = self.env['fm.purchase.request'].with_user(self.u_req)
        found = Request.search([])
        self.assertIn(mine, found)
        self.assertNotIn(theirs, found)
        with self.assertRaises(AccessError):
            theirs.with_user(self.u_req).read(['purpose'])

    def test_manager_sees_what_they_approve(self):
        req = self._request()
        req.action_submit()
        found = self.env['fm.purchase.request'].with_user(self.u_mgr).search([])
        self.assertIn(req, found)
        other = self._request(user=self.u_other)
        self.assertNotIn(other, found)

    def test_cannot_delete_submitted(self):
        req = self._request()
        req.action_submit()
        with self.assertRaises(UserError):
            req.unlink()

    # ── approval ─────────────────────────────────────────────────────────

    def test_manager_approves(self):
        req = self._request()
        req.action_submit()
        req.with_user(self.u_mgr).action_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.approved_by_id, self.u_mgr)
        self.assertFalse(req.activity_ids, 'the activity was closed')

    def test_threshold_needs_validation(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_purchase_request.validation_threshold', '100')
        req = self._request()   # 195 > 100
        req.action_submit()
        req.with_user(self.u_mgr).action_approve()
        self.assertEqual(req.state, 'to_validate')
        with self.assertRaises(AccessError):
            req.with_user(self.u_mgr).action_validate()
        req.with_user(self.u_pm).action_validate()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.validated_by_id, self.u_pm)

    def test_threshold_zero_means_never(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_purchase_request.validation_threshold', '0')
        req = self._request()
        req.action_submit()
        req.with_user(self.u_mgr).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_reject_with_reason_and_resubmit(self):
        req = self._request()
        req.action_submit()
        wiz = self.env['fm.purchase.request.reject'].with_user(self.u_mgr).create({
            'request_id': req.id, 'reason': 'Use the one in the cupboard.'})
        wiz.action_confirm()
        self.assertEqual(req.state, 'rejected')
        self.assertEqual(req.reject_reason, 'Use the one in the cupboard.')
        self.assertEqual(req.rejected_by_id, self.u_mgr)
        # The requester is told, by name.
        last = req.message_ids[0]
        self.assertIn('cupboard', last.body)
        self.assertIn(self.u_req.partner_id, last.partner_ids)
        # ...and can fix it and try again.
        req.with_user(self.u_req).action_draft()
        self.assertEqual(req.state, 'draft')
        self.assertFalse(req.reject_reason)

    def test_purchase_manager_can_approve_anything(self):
        req = self._request()
        req.action_submit()
        req.with_user(self.u_pm).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_requester_cancels_while_waiting(self):
        req = self._request()
        req.action_submit()
        req.with_user(self.u_req).action_cancel()
        self.assertEqual(req.state, 'cancelled')
        self.assertFalse(req.activity_ids)

    # ── purchasing ───────────────────────────────────────────────────────

    def _approved(self, **kw):
        """An approved request, returned in the BUYER's environment: from
        here on the tests look at purchase orders, which the requester is
        rightly not allowed to open."""
        req = self._request(**kw)
        req.action_submit()
        req.with_user(self.u_mgr).action_approve()
        return req.with_user(self.u_buy)

    def test_wizard_needs_product_and_vendor(self):
        req = self._approved()
        wiz = self._wizard(req)
        with self.assertRaises(UserError):
            wiz.action_create()

    def test_wizard_refuses_non_buyer(self):
        req = self._approved()
        with self.assertRaises(AccessError):
            self.env['fm.purchase.request.make.po'].with_user(self.u_req).with_context(
                active_model='fm.purchase.request', active_ids=req.ids).create({})

    def test_one_order_per_vendor_with_links_both_ways(self):
        req = self._approved()
        wiz = self._wizard(req)
        l1, l2 = wiz.line_ids
        l1.write({'product_id': self.product.id, 'vendor_id': self.vendor_a.id})
        l2.write({'product_id': self.product.id, 'vendor_id': self.vendor_b.id})
        wiz.action_create()
        orders = req.purchase_order_ids
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders.mapped('partner_id'), self.vendor_a | self.vendor_b)
        self.assertEqual(req.purchase_count, 2)
        self.assertEqual(req.state, 'ordered')
        self.assertEqual(req.purchase_state, 'ordered')
        for order in orders:
            self.assertEqual(order.origin, req.name)
            self.assertEqual(order.fm_request_ids, req)
            self.assertEqual(order.fm_request_count, 1)
        pol = orders.order_line.filtered(lambda l: l.fm_request_line_id == req.line_ids[0])
        self.assertEqual(pol.name, 'HDMI cable 2 m', "the requester's words stay on the order")
        self.assertEqual(pol.product_qty, 2)
        self.assertEqual(pol.price_unit, 60.0, 'the estimate is used when given')
        # written back to the request line
        self.assertEqual(req.line_ids[0].product_id, self.product)
        self.assertEqual(req.line_ids[0].vendor_id, self.vendor_a)
        self.assertEqual(req.line_ids[0].qty_ordered, 2)

    def test_merge_into_open_rfq(self):
        existing = self.env['purchase.order'].create({'partner_id': self.vendor_a.id})
        req = self._approved()
        wiz = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        self.assertTrue(wiz.merge_draft_po)
        wiz.action_create()
        self.assertEqual(req.purchase_order_ids, existing)
        self.assertEqual(len(existing.order_line), 2)
        self.assertEqual(existing.origin, req.name)

    def test_no_merge_when_asked(self):
        existing = self.env['purchase.order'].create({'partner_id': self.vendor_a.id})
        req = self._approved()
        wiz = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        wiz.merge_draft_po = False
        wiz.action_create()
        self.assertNotEqual(req.purchase_order_ids, existing)

    def test_no_merge_into_confirmed_order(self):
        confirmed = self.env['purchase.order'].create({
            'partner_id': self.vendor_a.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 1})]})
        confirmed.button_confirm()
        req = self._approved()
        wiz = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        wiz.action_create()
        self.assertNotEqual(req.purchase_order_ids, confirmed)

    def test_partial_order_then_the_rest(self):
        req = self._approved()
        wiz = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        wiz.line_ids[0].product_qty = 1   # of 2
        wiz.line_ids[1].product_qty = 0   # skip for now
        wiz.action_create()
        self.assertEqual(req.state, 'approved', 'not everything is ordered yet')
        self.assertEqual(req.purchase_state, 'partial')
        self.assertEqual(req.line_ids[0].qty_ordered, 1)
        wiz2 = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        self.assertEqual(wiz2.line_ids.filtered(lambda l: l.request_line_id == req.line_ids[0]).product_qty, 1,
                         'the remaining quantity is proposed')
        wiz2.action_create()
        self.assertEqual(req.state, 'ordered')

    def test_create_products_for_items_without_one(self):
        req = self._approved()
        wiz = self._wizard(req, vendor_id=self.vendor_a.id)
        wiz.line_ids[0].product_id = self.product   # this one is known
        self.assertFalse(wiz.line_ids[1].product_id)
        with self.assertRaises(UserError):
            wiz.action_create()                     # not without the tick
        wiz.create_missing_products = True
        wiz.action_create()
        made = req.line_ids[1].product_id
        self.assertEqual(made.name, 'Whiteboard markers, box')
        self.assertTrue(made.purchase_ok)
        self.assertFalse(made.sale_ok)
        self.assertEqual(req.line_ids[0].product_id, self.product, 'the known one was left alone')
        self.assertEqual(req.state, 'ordered')

    def test_many_requests_one_wizard(self):
        r1 = self._approved()
        r2 = self._approved(purpose='Another')
        wiz = self._wizard(r1 | r2, product_id=self.product.id, vendor_id=self.vendor_a.id)
        wiz.action_create()
        order = r1.purchase_order_ids
        self.assertEqual(order, r2.purchase_order_ids)
        self.assertEqual(len(order.order_line), 4)
        self.assertEqual(order.fm_request_ids, r1 | r2)
        self.assertEqual(order.fm_request_count, 2)
        self.assertIn(r1.name, order.origin)
        self.assertIn(r2.name, order.origin)

    def test_confirming_the_order_tells_the_requester(self):
        req = self._approved()
        self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        order = req.purchase_order_ids
        before = len(req.message_ids)
        order.with_user(self.u_buy).button_confirm()
        self.assertEqual(len(req.message_ids), before + 1)
        self.assertIn(order.name, req.message_ids[0].body)

    def test_requester_reads_ordered_request(self):
        """The whole point: a requester with no purchase rights opens their
        request after purchasing ordered it, and sees the order number."""
        req = self._approved()
        self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        mine = req.with_user(self.u_req)
        data = mine.read(['state', 'purchase_state', 'purchase_count', 'purchase_order_names',
                          'line_ids', 'amount_estimated'])[0]
        self.assertEqual(data['state'], 'ordered')
        self.assertEqual(data['purchase_count'], 1)
        self.assertEqual(data['purchase_order_names'], req.purchase_order_ids.name)
        with self.assertRaises(AccessError):
            mine.read(['purchase_order_ids'])
        lines = mine.line_ids.read(['qty_ordered', 'qty_received', 'purchase_state'])
        self.assertEqual(lines[0]['qty_ordered'], 2)

    def test_received_by_requester(self):
        req = self._approved()
        self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        with self.assertRaises(AccessError):
            req.with_user(self.u_other).action_receive()
        req.with_user(self.u_req).action_receive()
        self.assertEqual(req.state, 'received')

    def test_cancelled_purchase_order_does_not_count(self):
        req = self._approved()
        self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        req.purchase_order_ids.button_cancel()
        self.assertEqual(req.line_ids[0].qty_ordered, 0)
        self.assertEqual(req.purchase_state, 'none')

    def test_uom_conversion_back_to_request(self):
        dozen = self.env.ref('uom.product_uom_dozen')
        req = self._request(lines=[{'name': 'Pens', 'product_qty': 24, 'product_uom_id': self.unit.id}])
        req.action_submit(); req.with_user(self.u_mgr).action_approve()
        wiz = self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id)
        wiz.line_ids.write({'product_qty': 2, 'product_uom_id': dozen.id})
        wiz.action_create()
        self.assertEqual(req.line_ids.qty_ordered, 24, '2 dozen is 24 units to the requester')
        self.assertEqual(req.state, 'ordered')

    def test_user_without_email_can_do_everything(self):
        """Logins like "rina" are normal. Odoo refuses to post a message for
        a user with no email; none of this module's steps may fall over it."""
        self.u_req.partner_id.email = False
        self.u_mgr.partner_id.email = False
        req = self._request()
        req.action_submit()
        self.assertEqual(req.state, 'submitted')
        self.assertTrue(req.activity_ids, 'the activity exists even without the email')
        req.with_user(self.u_mgr).action_approve()
        self.assertEqual(req.state, 'approved')
        buyer = req.with_user(self.u_buy)
        self._wizard(buyer, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        self.assertEqual(req.state, 'ordered')
        req.with_user(self.u_req).action_receive()
        self.assertEqual(req.state, 'received')
        req2 = self._request()
        req2.action_submit()
        self.env['fm.purchase.request.reject'].with_user(self.u_mgr).create({
            'request_id': req2.id, 'reason': 'No.'}).action_confirm()
        self.assertEqual(req2.state, 'rejected')
        req2.with_user(self.u_req).action_draft()
        req2.with_user(self.u_req).action_cancel()
        self.assertEqual(req2.state, 'cancelled')

    # ── multi-company ────────────────────────────────────────────────────

    def test_multi_company_isolation(self):
        """A group of companies: a buyer of company B never sees company
        A's requests, and an order made from an A request is an A order."""
        company_b = self.env['res.company'].create({'name': 'Company B'})
        u_buy_b = new_test_user(self.env, login='pr_buy_b',
                                groups='base.group_user,purchase.group_purchase_user',
                                company_id=company_b.id, company_ids=[(6, 0, company_b.ids)])
        req = self._approved()                       # company A (self.company)
        self.assertEqual(req.company_id, self.company)
        Request = self.env['fm.purchase.request'].with_user(u_buy_b)
        self.assertNotIn(req, Request.search([]), 'a buyer of B does not see A')
        with self.assertRaises(AccessError):
            req.with_user(u_buy_b).read(['purpose'])
        # Ordering from A stays in A, whoever the buyer is allowed to see.
        self._wizard(req, product_id=self.product.id, vendor_id=self.vendor_a.id).action_create()
        self.assertEqual(req.purchase_order_ids.company_id, self.company)
        # A requester employed by B makes B requests.
        e_b = self.env['hr.employee'].create({
            'name': 'Req B', 'user_id': u_buy_b.id, 'company_id': company_b.id})
        req_b = self.env['fm.purchase.request'].with_user(u_buy_b).with_company(company_b).create({
            'purpose': 'B thing', 'line_ids': [(0, 0, {'name': 'x', 'product_qty': 1})]})
        self.assertEqual(req_b.company_id, company_b)
        self.assertEqual(req_b.requester_id, e_b)
        self.assertNotIn(req_b, self.env['fm.purchase.request'].with_user(self.u_buy).search([]))

    def test_report_renders(self):
        req = self._approved()
        html = self.env['ir.actions.report']._render_qweb_html(
            'fm_purchase_request.report_purchase_request', req.ids)[0]
        self.assertIn(req.name.encode(), html)
        self.assertIn(b'HDMI cable 2 m', html)
