# -*- coding: utf-8 -*-
"""A correction must do exactly one thing: move the attendance, once, with
somebody's name on it."""

from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAttendanceCorrection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': "Warung Kopi"})
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.env.user.tz = 'UTC'
        cls.calendar = cls.env['resource.calendar'].create({
            'name': "Shop hours", 'tz': 'UTC', 'company_id': cls.company.id})
        cls.company.resource_calendar_id = cls.calendar
        cls.boss, cls.user_boss = cls._employee("Bea Boss", 'fmac_bea')
        cls.worker, cls.user_worker = cls._employee("Wira Worker", 'fmac_wira', parent=cls.boss)
        cls.officer = cls._user("Ola Officer", 'fmac_ola', officer=True)
        day = fields.Date.context_today(cls.env.user) - timedelta(days=2)
        while day.weekday() > 4:
            day -= timedelta(days=1)
        cls.day = day

    @classmethod
    def _groups(cls, xmlids):
        key = 'group_ids' if 'group_ids' in cls.env['res.users']._fields else 'groups_id'
        return {key: [(6, 0, [cls.env.ref(x).id for x in xmlids])]}

    @classmethod
    def _user(cls, name, login, officer=False):
        groups = ['base.group_user', 'fm_attendance_correction.group_attendance_correction_user']
        if officer:
            groups.append('fm_attendance_correction.group_attendance_correction_officer')
        return cls.env['res.users'].create({
            'name': name, 'login': login, 'email': '%s@example.com' % login, 'tz': 'UTC',
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            **cls._groups(groups)})

    @classmethod
    def _employee(cls, name, login, parent=None):
        user = cls._user(name, login)
        employee = cls.env['hr.employee'].create({
            'name': name, 'user_id': user.id, 'company_id': cls.company.id, 'tz': 'UTC',
            'parent_id': parent.id if parent else False})
        return employee, user

    def _at(self, hour, day=None):
        return datetime.combine(day or self.day, datetime.min.time()) + timedelta(hours=hour)

    def _request(self, user=None, **values):
        base = {'kind': 'check_in', 'date': self.day, 'check_in': self._at(8),
                'reason': "The badge reader was down."}
        base.update(values)
        return self.env['fm.attendance.correction'].with_user(user or self.user_worker).create(base)

    # ── filing ───────────────────────────────────────────────────────────
    def test_a_request_takes_a_reference_and_the_filers_own_employee(self):
        request = self._request()
        self.assertTrue(request.name.startswith('AC/'))
        self.assertEqual(request.employee_id, self.worker)
        self.assertEqual(request.manager_id, self.boss, "the manager comes from the org chart")
        self.assertEqual(request.state, 'draft')

    def test_nobody_files_for_somebody_else(self):
        request = self._request(employee_id=self.boss.id)
        self.assertEqual(request.employee_id, self.worker, "the employee is forced to the filer")

    def test_an_officer_may_file_for_somebody_else(self):
        request = self._request(user=self.officer, employee_id=self.worker.id)
        self.assertEqual(request.employee_id, self.worker)

    def test_a_user_without_an_employee_cannot_file(self):
        stranger = self._user("No Employee", 'fmac_none')
        with self.assertRaises(UserError):
            self._request(user=stranger)

    def test_the_future_is_not_a_correction(self):
        with self.assertRaises(ValidationError):
            self._request(date=fields.Date.context_today(self.env.user) + timedelta(days=1),
                          check_in=self._at(8, fields.Date.context_today(self.env.user) + timedelta(days=1)))

    def test_check_out_must_follow_check_in(self):
        with self.assertRaises(ValidationError):
            self._request(kind='both', check_in=self._at(17), check_out=self._at(8))

    def test_corrections_do_not_go_back_for_ever(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_attendance_correction.days_back', '7')
        old = fields.Date.context_today(self.env.user) - timedelta(days=30)
        with self.assertRaises(ValidationError):
            self._request(date=old, check_in=self._at(8, old))

    # ── the chain ────────────────────────────────────────────────────────
    def test_submitting_goes_to_the_manager(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        self.assertEqual(request.state, 'to_approve')
        self.assertTrue(self.env['mail.activity'].search_count([
            ('res_id', '=', request.id), ('user_id', '=', self.user_boss.id)]),
            "the manager is actually asked")

    def test_without_a_manager_it_goes_straight_to_hr(self):
        self.worker.parent_id = False
        request = self._request()
        request.invalidate_recordset()
        request.with_user(self.user_worker).action_submit()
        self.assertEqual(request.state, 'to_validate')

    def test_only_the_manager_or_an_officer_approves(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        other, user_other = self._employee("Someone Else", 'fmac_other')
        with self.assertRaises(AccessError):
            request.with_user(user_other).action_approve()
        request.with_user(self.user_boss).action_approve()
        self.assertEqual(request.state, 'to_validate')
        self.assertEqual(request.approved_by, self.user_boss)

    def test_only_an_officer_validates(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        request.with_user(self.user_boss).action_approve()
        with self.assertRaises(AccessError):
            request.with_user(self.user_boss).action_validate()
        request.with_user(self.officer).action_validate()
        self.assertEqual(request.state, 'done')

    def test_the_hr_step_can_be_switched_off(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_attendance_correction.require_hr', 'False')
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        request.with_user(self.user_boss).action_approve()
        self.assertEqual(request.state, 'done', "the manager's word is enough")
        self.assertTrue(request.attendance_id)

    # ── what it writes ───────────────────────────────────────────────────
    def _approved(self, **values):
        request = self._request(**values)
        request.with_user(self.user_worker).action_submit()
        request.with_user(self.user_boss).action_approve()
        request.with_user(self.officer).action_validate()
        return request

    def test_a_missed_check_in_creates_the_attendance(self):
        request = self._approved()
        attendance = request.attendance_id
        self.assertTrue(attendance)
        self.assertEqual(attendance.employee_id, self.worker)
        self.assertEqual(attendance.check_in, self._at(8))
        self.assertTrue(attendance.check_out, "a past day is closed, not left running")

    def test_a_forgotten_check_in_is_closed_at_the_end_of_the_schedule(self):
        request = self._approved()
        # The shop closes at 17:00 in the standard calendar.
        self.assertEqual(request.attendance_id.check_out.hour, 17)

    def test_a_missed_check_out_closes_the_attendance_that_is_open(self):
        open_one = self.env['hr.attendance'].create({
            'employee_id': self.worker.id, 'check_in': self._at(8)})
        request = self._approved(kind='check_out', check_in=False, check_out=self._at(17))
        self.assertEqual(request.attendance_id, open_one, "it closes the open one")
        self.assertEqual(open_one.check_out, self._at(17))
        self.assertEqual(self.env['hr.attendance'].search_count([
            ('employee_id', '=', self.worker.id)]), 1, "and does not add a second")

    def test_both_missed_creates_one_attendance_with_both_ends(self):
        request = self._approved(kind='both', check_in=self._at(8), check_out=self._at(16))
        self.assertEqual(request.attendance_id.check_in, self._at(8))
        self.assertEqual(request.attendance_id.check_out, self._at(16))
        # Odoo counts the worked hours against the schedule, lunch break
        # deducted - which is the point of letting Odoo compute them.
        self.assertGreater(request.attendance_id.worked_hours, 6.0)

    def test_closing_an_attendance_that_was_never_opened_is_refused(self):
        request = self._request(kind='check_out', check_in=False, check_out=self._at(17))
        with self.assertRaises(UserError):
            request.with_user(self.user_worker).action_submit()

    def test_an_overlapping_attendance_stops_the_request_at_the_door(self):
        self.env['hr.attendance'].create({
            'employee_id': self.worker.id, 'check_in': self._at(7), 'check_out': self._at(12)})
        request = self._request(check_in=self._at(8))
        with self.assertRaises(UserError):
            request.with_user(self.user_worker).action_submit()

    def test_a_request_for_today_leaves_the_attendance_open(self):
        today = fields.Date.context_today(self.env.user)
        now = fields.Datetime.now()
        request = self._approved(date=today, check_in=now - timedelta(hours=1))
        self.assertFalse(request.attendance_id.check_out,
                         "still working: the employee clocks out normally")

    # ── refusing and undoing ─────────────────────────────────────────────
    def test_refusing_needs_a_reason_and_leaves_the_attendance_alone(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        before = self.env['hr.attendance'].search_count([('employee_id', '=', self.worker.id)])
        wizard = self.env['fm.attendance.correction.refuse'].with_user(self.user_boss).create({
            'request_id': request.id, 'reason': "The gate log says 09:40."})
        wizard.action_refuse()
        self.assertEqual(request.state, 'refused')
        self.assertIn("09:40", request.refuse_reason)
        self.assertEqual(self.env['hr.attendance'].search_count(
            [('employee_id', '=', self.worker.id)]), before)

    def test_a_refused_request_can_be_filed_again(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        self.env['fm.attendance.correction.refuse'].with_user(self.user_boss).create({
            'request_id': request.id, 'reason': "Wrong day."}).action_refuse()
        request.with_user(self.user_worker).action_reset()
        self.assertEqual(request.state, 'draft')
        self.assertFalse(request.refuse_reason)

    def test_a_request_in_flight_cannot_be_deleted(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.officer).unlink()
        request.with_user(self.user_worker).action_cancel()
        request.with_user(self.officer).unlink()

    def test_the_hours_cannot_be_edited_after_submitting(self):
        request = self._request()
        request.with_user(self.user_worker).action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.user_worker).write({'check_in': self._at(7)})

    # ── who sees what ────────────────────────────────────────────────────
    def test_an_employee_sees_only_their_own(self):
        mine = self._request()
        other, user_other = self._employee("Third Person", 'fmac_third')
        theirs = self._request(user=user_other)
        seen = self.env['fm.attendance.correction'].with_user(self.user_worker).search([])
        self.assertIn(mine, seen)
        self.assertNotIn(theirs, seen)

    def test_a_manager_sees_their_teams(self):
        mine = self._request()
        seen = self.env['fm.attendance.correction'].with_user(self.user_boss).search([])
        self.assertIn(mine, seen, "a manager has to read what they are asked to approve")

    def test_an_officer_sees_everything(self):
        mine = self._request()
        other, user_other = self._employee("Fourth Person", 'fmac_fourth')
        theirs = self._request(user=user_other)
        seen = self.env['fm.attendance.correction'].with_user(self.officer).search([])
        self.assertIn(mine, seen)
        self.assertIn(theirs, seen)
