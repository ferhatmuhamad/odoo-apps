# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged, new_test_user

from ..models import geo

HQ = (-7.6618163, 110.6708992)          # a real office in Central Java
BRANCH = (-7.7956, 110.3695)            # Yogyakarta, ~35 km west

# Roughly one degree of latitude is 111 km, so these are ~14 m and ~1 km
# north of the HQ pin.
NEAR = (HQ[0] + 0.000126, HQ[1])
FAR = (HQ[0] + 0.009, HQ[1])


@tagged('post_install', '-at_install')
class TestGeofence(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.hq = cls.env['hr.work.location'].create({
            'name': 'Head Office', 'address_id': cls.company.partner_id.id,
            'fm_geo_enabled': True, 'fm_geo_latitude': HQ[0], 'fm_geo_longitude': HQ[1],
            'fm_geo_radius': 100, 'fm_geo_policy': 'record',
        })
        cls.branch = cls.env['hr.work.location'].create({
            'name': 'Yogyakarta Branch', 'address_id': cls.company.partner_id.id,
            'fm_geo_enabled': True, 'fm_geo_latitude': BRANCH[0], 'fm_geo_longitude': BRANCH[1],
            'fm_geo_radius': 150, 'fm_geo_policy': 'reason',
        })
        cls.user = new_test_user(cls.env, login='geo_emp', groups='base.group_user')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Geo Employee', 'user_id': cls.user.id,
            'work_location_id': cls.hq.id, 'company_id': cls.company.id,
        })

    # ── arithmetic ───────────────────────────────────────────────────────

    def test_distance(self):
        self.assertAlmostEqual(geo.distance_m(*HQ, *NEAR), 14.0, delta=0.5)
        self.assertAlmostEqual(geo.distance_m(*HQ, *FAR), 1000.0, delta=3.0)
        self.assertEqual(geo.distance_m(*HQ, *HQ), 0.0)
        self.assertFalse(geo.valid(0, 0))
        self.assertFalse(geo.valid(False, False))
        self.assertFalse(geo.valid(91, 0))
        self.assertTrue(geo.valid(*HQ))

    # ── verdicts ─────────────────────────────────────────────────────────

    def test_verdict_in_out_unknown(self):
        v = self.employee._fm_geo_evaluate(*NEAR)
        self.assertEqual(v['status'], 'in')
        self.assertEqual(v['location'], self.hq)
        self.assertIsNone(v['policy'])

        v = self.employee._fm_geo_evaluate(*FAR)
        self.assertEqual(v['status'], 'out')
        self.assertEqual(v['location'], self.hq)
        self.assertEqual(v['policy'], 'record')
        self.assertAlmostEqual(v['distance'], 1000.0, delta=3.0)

        v = self.employee._fm_geo_evaluate(False, False)
        self.assertEqual(v['status'], 'unknown')
        self.assertEqual(v['location'], self.hq)

    def test_verdict_no_fence_no_status(self):
        loner = self.env['hr.employee'].create({'name': 'No Fence', 'company_id': self.company.id})
        self.assertFalse(loner._fm_geo_evaluate(*NEAR)['status'])

    def test_verdict_exempt(self):
        self.employee.fm_geo_exempt = True
        v = self.employee._fm_geo_evaluate(*FAR)
        self.assertEqual(v['status'], 'exempt')
        self.assertIsNone(v['policy'])
        # The office is still named, so HR can see where they were.
        self.assertEqual(v['location'], self.hq)

    def test_verdict_extra_location_and_nearest_edge(self):
        """Inside ANY allowed fence is in - and the fence chosen is the one
        the person is inside, not the one whose centre is nearest."""
        self.employee.fm_geo_extra_location_ids = self.branch
        v = self.employee._fm_geo_evaluate(BRANCH[0] + 0.0005, BRANCH[1])   # ~55 m from branch
        self.assertEqual(v['status'], 'in')
        self.assertEqual(v['location'], self.branch)

        # A wide fence (radius 500) with a narrow one (radius 50) 300 m away.
        wide = self.env['hr.work.location'].create({
            'name': 'Wide', 'address_id': self.company.partner_id.id, 'fm_geo_enabled': True,
            'fm_geo_latitude': HQ[0], 'fm_geo_longitude': HQ[1], 'fm_geo_radius': 500,
        })
        narrow = self.env['hr.work.location'].create({
            'name': 'Narrow', 'address_id': self.company.partner_id.id, 'fm_geo_enabled': True,
            'fm_geo_latitude': HQ[0] + 0.0063, 'fm_geo_longitude': HQ[1], 'fm_geo_radius': 50,
        })
        self.employee.write({'work_location_id': wide.id, 'fm_geo_extra_location_ids': [(6, 0, narrow.ids)]})
        # 400 m from the wide centre (inside), 300 m from the narrow centre (outside).
        point = (HQ[0] + 0.0036, HQ[1])
        v = self.employee._fm_geo_evaluate(*point)
        self.assertEqual(v['status'], 'in')
        self.assertEqual(v['location'], wide)

    def test_policy_of_nearest_applies_when_outside_all(self):
        self.employee.fm_geo_extra_location_ids = self.branch
        # 1 km from the branch, 35 km from HQ: the branch's 'reason' policy.
        v = self.employee._fm_geo_evaluate(BRANCH[0] + 0.009, BRANCH[1])
        self.assertEqual(v['status'], 'out')
        self.assertEqual(v['location'], self.branch)
        self.assertEqual(v['policy'], 'reason')

    # ── enforcement ──────────────────────────────────────────────────────

    def _decide(self, point, policy, mode, reason=None):
        self.hq.fm_geo_policy = policy
        v = self.employee._fm_geo_evaluate(*point)
        return self.employee._fm_geo_enforce(v, mode, reason=reason)

    def test_enforce_matrix(self):
        ok = lambda d: self.assertEqual(d['action'], 'ok')
        # In area: always fine.
        for policy in ('record', 'reason', 'block'):
            for mode in ('systray', 'kiosk'):
                ok(self._decide(NEAR, policy, mode))
        # Record: fine anywhere.
        ok(self._decide(FAR, 'record', 'systray'))
        ok(self._decide((False, False), 'record', 'kiosk'))
        # Block.
        self.assertEqual(self._decide(FAR, 'block', 'systray')['action'], 'block')
        self.assertEqual(self._decide(FAR, 'block', 'kiosk')['action'], 'block')
        self.assertEqual(self._decide((False, False), 'block', 'systray')['action'], 'block')
        d = self._decide((False, False), 'block', 'kiosk')
        ok(d)
        self.assertTrue(d['note'], 'a kiosk without a position is recorded, with a note')
        # Reason.
        self.assertEqual(self._decide(FAR, 'reason', 'systray')['action'], 'reason')
        ok(self._decide(FAR, 'reason', 'systray', reason='client visit'))
        d = self._decide(FAR, 'reason', 'kiosk')
        ok(d)
        self.assertIn('kiosk', d['note'])

    def test_block_message_names_distance_and_place(self):
        d = self._decide(FAR, 'block', 'systray')
        self.assertIn('1.0 km', d['message'])
        self.assertIn('Head Office', d['message'])
        self.assertIn('100 m', d['message'])

    # ── the real thing: _attendance_action_change ────────────────────────

    def _check_in(self, point, mode='systray'):
        info = {'mode': mode}
        if point[0]:
            info.update(latitude=point[0], longitude=point[1])
        return self.employee._attendance_action_change(info)

    def test_check_in_records_verdict(self):
        att = self._check_in(NEAR)
        self.assertEqual(att.in_fm_geo_status, 'in')
        self.assertEqual(att.in_fm_geo_location_id, self.hq)
        self.assertAlmostEqual(att.in_fm_geo_distance, 14.0, delta=0.5)
        self.assertEqual(att.in_fm_geo_fence['radius'], 100)
        self.assertEqual(att.in_fm_geo_fence['name'], 'Head Office')
        self.assertFalse(att.in_fm_geo_flagged)
        self.assertFalse(att.out_fm_geo_status)

        out = self._check_in(FAR)   # now a check-out, from 1 km away
        self.assertEqual(out, att)
        self.assertEqual(att.out_fm_geo_status, 'out')
        self.assertAlmostEqual(att.out_fm_geo_distance, 1000.0, delta=3.0)

    def test_check_in_blocked(self):
        self.hq.fm_geo_policy = 'block'
        with self.assertRaises(UserError):
            self._check_in(FAR)
        self.assertFalse(self.env['hr.attendance'].search([('employee_id', '=', self.employee.id)]))
        # Kiosk with a position: blocked too.
        with self.assertRaises(UserError):
            self._check_in(FAR, mode='kiosk')
        # Kiosk without one: recorded, noted.
        att = self._check_in((False, False), mode='kiosk')
        self.assertEqual(att.in_fm_geo_status, 'unknown')
        self.assertTrue(att.in_fm_geo_note)

    def test_check_in_reason_required_then_given(self):
        self.hq.fm_geo_policy = 'reason'
        with self.assertRaises(UserError):
            self._check_in(FAR)
        # What the systray does: precheck with a reason, then the check-in.
        self.employee.fm_geo_pending = {
            'reason': 'Client visit', 'accuracy': 12.0, 'speed': 0,
            'position_time': None, 'at': fields.Datetime.now().isoformat(),
        }
        att = self._check_in(FAR)
        self.assertEqual(att.in_fm_geo_status, 'out')
        self.assertEqual(att.in_fm_geo_reason, 'Client visit')
        self.assertFalse(self.employee.fm_geo_pending, 'consumed')

    def test_stale_pending_is_ignored(self):
        self.hq.fm_geo_policy = 'reason'
        self.employee.fm_geo_pending = {
            'reason': 'old', 'at': (fields.Datetime.now() - timedelta(minutes=6)).isoformat(),
        }
        with self.assertRaises(UserError):
            self._check_in(FAR)

    def test_kiosk_reason_policy_records_with_note(self):
        self.hq.fm_geo_policy = 'reason'
        att = self._check_in(FAR, mode='kiosk')
        self.assertEqual(att.in_fm_geo_status, 'out')
        self.assertIn('kiosk', att.in_fm_geo_note)

    def test_no_mode_means_no_verdict(self):
        att = self.employee._attendance_action_change()
        self.assertFalse(att.in_fm_geo_status)

    def test_exempt_never_blocked(self):
        self.hq.fm_geo_policy = 'block'
        self.employee.fm_geo_exempt = True
        att = self._check_in(FAR)
        self.assertEqual(att.in_fm_geo_status, 'exempt')

    # ── precheck as an ordinary user ─────────────────────────────────────

    def test_precheck_as_plain_user(self):
        """An employee with no HR rights at all can ask about themselves,
        and only themselves."""
        Employee = self.env['hr.employee'].with_user(self.user)
        self.hq.fm_geo_policy = 'reason'
        r = Employee.fm_geo_precheck(latitude=NEAR[0], longitude=NEAR[1], accuracy=8.0)
        self.assertEqual(r['action'], 'ok')
        self.assertEqual(self.employee.fm_geo_pending['accuracy'], 8.0)

        r = Employee.fm_geo_precheck(latitude=FAR[0], longitude=FAR[1])
        self.assertEqual(r['action'], 'reason')
        self.assertIn('Head Office', r['message'])

        r = Employee.fm_geo_precheck(latitude=FAR[0], longitude=FAR[1], reason='  Site survey ')
        self.assertEqual(r['action'], 'ok')
        self.assertEqual(self.employee.fm_geo_pending['reason'], 'Site survey')

        self.hq.fm_geo_policy = 'block'
        r = Employee.fm_geo_precheck(latitude=FAR[0], longitude=FAR[1])
        self.assertEqual(r['action'], 'block')

    def test_precheck_without_employee(self):
        other = new_test_user(self.env, login='geo_nobody', groups='base.group_user')
        r = self.env['hr.employee'].with_user(other).fm_geo_precheck(latitude=FAR[0], longitude=FAR[1])
        self.assertEqual(r['action'], 'ok')

    # ── suspicion ────────────────────────────────────────────────────────

    def test_flag_zero_accuracy(self):
        self.employee.fm_geo_pending = {'accuracy': 0, 'at': fields.Datetime.now().isoformat()}
        att = self._check_in(NEAR)
        self.assertTrue(att.in_fm_geo_flagged)
        self.assertIn('0 m', att.in_fm_geo_note)
        self.assertTrue(att.fm_geo_flagged)

    def test_flag_low_accuracy_and_speed(self):
        self.employee.fm_geo_pending = {
            'accuracy': 900, 'speed': 60, 'at': fields.Datetime.now().isoformat()}
        att = self._check_in(NEAR)
        self.assertTrue(att.in_fm_geo_flagged)
        self.assertIn('900 m', att.in_fm_geo_note)
        self.assertIn('216 km/h', att.in_fm_geo_note)

    def test_flag_teleport_between_check_in_and_out(self):
        att = self._check_in(NEAR)
        # Five minutes later, a check-out from the Yogyakarta branch, 35 km away.
        att.check_in = fields.Datetime.now() - timedelta(minutes=5)
        out = self._check_in(BRANCH)
        self.assertEqual(out, att)
        self.assertTrue(att.out_fm_geo_flagged)
        self.assertIn('km/h', att.out_fm_geo_note)
        self.assertIn('check-in', att.out_fm_geo_note)
        self.assertFalse(att.in_fm_geo_flagged, 'the check-in itself was fine')

    def test_no_flag_for_a_plausible_journey(self):
        att = self._check_in(NEAR)
        att.check_in = fields.Datetime.now() - timedelta(hours=2)
        self._check_in(BRANCH)
        self.assertFalse(att.out_fm_geo_flagged)

    # ── re-evaluation and the day map ────────────────────────────────────

    def test_evaluate_again_after_moving_the_radius(self):
        att = self._check_in(FAR)
        self.assertEqual(att.in_fm_geo_status, 'out')
        self.hq.fm_geo_radius = 1200
        att.action_fm_geo_evaluate()
        self.assertEqual(att.in_fm_geo_status, 'in')
        self.assertEqual(att.in_fm_geo_fence['radius'], 1200)
        self.assertIn('Evaluated again', att.in_fm_geo_note)

    def test_evaluate_skips_manual_attendances(self):
        att = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': fields.Datetime.now() - timedelta(hours=1)})
        att.action_fm_geo_evaluate()
        self.assertFalse(att.in_fm_geo_status)

    def test_day_map_data(self):
        # Counted against what was there before: the map is of the whole
        # company's day, and a database used for anything else has other
        # people's check-ins on it too.
        before = self.env['hr.attendance'].fm_geo_map_data()
        self._check_in(FAR)
        data = self.env['hr.attendance'].fm_geo_map_data()
        mine = [p for p in data['points'] if p['employee_id'] == self.employee.id]
        self.assertEqual(len(mine), 1)
        p = mine[0]
        self.assertEqual(p['employee'], 'Geo Employee')
        self.assertEqual(p['status'], 'out')
        self.assertEqual(p['location'], 'Head Office')
        self.assertAlmostEqual(p['distance'], 1000.0, delta=3.0)
        self.assertEqual(data['summary']['out'], before['summary']['out'] + 1)
        self.assertEqual(data['summary']['total'], before['summary']['total'] + 1)
        self.assertTrue(any(f['name'] == 'Head Office' for f in data['fences']))

    def test_use_address_coordinates(self):
        self.company.partner_id.write({'partner_latitude': 1.5, 'partner_longitude': 103.8})
        loc = self.env['hr.work.location'].create({
            'name': 'From address', 'address_id': self.company.partner_id.id})
        loc.action_fm_geo_use_address()
        self.assertEqual((loc.fm_geo_latitude, loc.fm_geo_longitude), (1.5, 103.8))
        self.company.partner_id.write({'partner_latitude': 0, 'partner_longitude': 0})
        with self.assertRaises(UserError):
            loc.action_fm_geo_use_address()
