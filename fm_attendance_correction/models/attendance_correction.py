# -*- coding: utf-8 -*-
"""Somebody forgot to clock in. Now what?

Without this, the fix is a message to HR and a hand-edited attendance -
no record of who asked, who agreed, or why the hours changed. Here the
employee files the correction themselves, their manager approves it, HR
validates it, and only then does the attendance move. The chatter keeps
the whole conversation attached to the record it changed.
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

OFFICER_GROUP = 'fm_attendance_correction.group_attendance_correction_officer'


class AttendanceCorrection(models.Model):
    _name = 'fm.attendance.correction'
    _description = "Attendance Correction Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", readonly=True, copy=False, default='/')
    state = fields.Selection([
        ('draft', "Draft"),
        ('to_approve', "Waiting for the manager"),
        ('to_validate', "Waiting for HR"),
        ('done', "Applied"),
        ('refused', "Refused"),
        ('cancel', "Cancelled"),
    ], default='draft', required=True, tracking=True, copy=False, index=True)

    kind = fields.Selection([
        ('check_in', "Forgot to check in"),
        ('check_out', "Forgot to check out"),
        ('both', "Forgot both"),
    ], string="What happened", default='check_in', required=True, tracking=True)

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True, tracking=True, ondelete='cascade',
        default=lambda self: self.env.user.employee_id)
    user_id = fields.Many2one(related='employee_id.user_id', store=True, index=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string="Manager", compute='_compute_manager',
                                 store=True, readonly=True)
    manager_user_id = fields.Many2one(related='manager_id.user_id', store=True, readonly=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, readonly=True)

    date = fields.Date(string="Day", required=True, default=fields.Date.context_today, tracking=True)
    check_in = fields.Datetime(string="Checked in at", tracking=True)
    check_out = fields.Datetime(string="Checked out at", tracking=True)
    reason = fields.Text(string="What happened", required=True,
                         help="The employee's own words. HR sees this before agreeing.")
    evidence = fields.Binary(string="Evidence", attachment=True, copy=False,
                             help="A photo of the gate log, a screenshot, an email - anything that helps.")
    evidence_filename = fields.Char(copy=False)

    attendance_id = fields.Many2one('hr.attendance', string="Attendance", readonly=True, copy=False,
                                    help="The attendance this request created or corrected.")
    worked_hours = fields.Float(related='attendance_id.worked_hours', string="Worked", readonly=True)

    approved_by = fields.Many2one('res.users', string="Approved by", readonly=True, copy=False)
    approved_on = fields.Datetime(string="Approved on", readonly=True, copy=False)
    validated_by = fields.Many2one('res.users', string="Validated by", readonly=True, copy=False)
    validated_on = fields.Datetime(string="Validated on", readonly=True, copy=False)
    refused_by = fields.Many2one('res.users', string="Refused by", readonly=True, copy=False)
    refuse_reason = fields.Text(string="Why it was refused", readonly=True, copy=False, tracking=True)

    # Who may press what, worked out once for the buttons and the rules.
    can_submit = fields.Boolean(compute='_compute_rights')
    can_approve = fields.Boolean(compute='_compute_rights')
    can_validate = fields.Boolean(compute='_compute_rights')
    can_refuse = fields.Boolean(compute='_compute_rights')
    can_cancel = fields.Boolean(compute='_compute_rights')
    can_reset = fields.Boolean(compute='_compute_rights')
    is_officer = fields.Boolean(compute='_compute_rights')

    # ── who is who ───────────────────────────────────────────────────────
    @api.depends('employee_id')
    def _compute_manager(self):
        for request in self:
            employee = request.employee_id.sudo()
            request.manager_id = employee.parent_id or employee.department_id.manager_id or False

    def _is_officer(self, user=None):
        # Code running as the superuser - a data import, a server action -
        # is not a person filing a request and must not be fenced in.
        if self.env.su and user is None:
            return True
        return (user or self.env.user).has_group(OFFICER_GROUP)

    def _is_owner(self, user=None):
        user = user or self.env.user
        return self.employee_id and self.employee_id.sudo().user_id == user

    @api.depends('state', 'employee_id', 'manager_user_id')
    def _compute_rights(self):
        user = self.env.user
        officer = self._is_officer()
        for request in self:
            owner = request._is_owner()
            is_manager = request.manager_user_id == user
            request.is_officer = officer
            request.can_submit = request.state == 'draft' and (owner or officer)
            request.can_approve = request.state == 'to_approve' and (is_manager or officer)
            request.can_validate = request.state == 'to_validate' and officer
            request.can_refuse = request.state in ('to_approve', 'to_validate') and (is_manager or officer)
            request.can_cancel = request.state in ('to_approve', 'to_validate') and (owner or officer)
            request.can_reset = request.state in ('refused', 'cancel') and (owner or officer)

    # ── settings ─────────────────────────────────────────────────────────
    def _days_back(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'fm_attendance_correction.days_back') or 14)
        except ValueError:
            return 14

    def _hr_step_required(self):
        return (self.env['ir.config_parameter'].sudo().get_param(
            'fm_attendance_correction.require_hr') or 'True') == 'True'

    # ── sanity ───────────────────────────────────────────────────────────
    @api.onchange('date', 'kind')
    def _onchange_date(self):
        """Offer the hours this employee was due to work that day."""
        for request in self:
            if not request.date or not request.employee_id:
                continue
            start, stop = request._scheduled_day()
            if request.kind in ('check_in', 'both') and not request.check_in and start:
                request.check_in = start
            if request.kind in ('check_out', 'both') and not request.check_out and stop:
                request.check_out = stop

    def _scheduled_day(self):
        """The working hours of that employee on that day, in UTC."""
        self.ensure_one()
        employee = self.employee_id.sudo()
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar or not self.date:
            return None, None
        tz = pytz.timezone(employee.tz or self.env.user.tz or 'UTC')
        day_start = tz.localize(datetime.combine(self.date, time.min)).astimezone(pytz.UTC)
        day_stop = tz.localize(datetime.combine(self.date, time.max)).astimezone(pytz.UTC)
        intervals = calendar._attendance_intervals_batch(
            day_start, day_stop, resources=employee.resource_id)
        found = intervals.get(employee.resource_id.id) or intervals.get(False) or []
        if not found:
            return None, None
        starts = [interval[0] for interval in found]
        stops = [interval[1] for interval in found]
        return (min(starts).astimezone(pytz.UTC).replace(tzinfo=None),
                max(stops).astimezone(pytz.UTC).replace(tzinfo=None))

    @api.constrains('kind', 'check_in', 'check_out', 'date')
    def _check_times(self):
        for request in self:
            if request.kind in ('check_in', 'both') and not request.check_in:
                raise ValidationError(_("Say what time you checked in."))
            if request.kind in ('check_out', 'both') and not request.check_out:
                raise ValidationError(_("Say what time you checked out."))
            if request.check_in and request.check_out and request.check_out <= request.check_in:
                raise ValidationError(_("The check-out has to come after the check-in."))
            now = fields.Datetime.now()
            for value in (request.check_in, request.check_out):
                if value and value > now:
                    raise ValidationError(_("That is in the future. A correction is for something "
                                            "that already happened."))
            if request.date and request.date > fields.Date.context_today(request):
                raise ValidationError(_("That day has not happened yet."))
            limit = request._days_back()
            if limit and request.date and request.date < fields.Date.context_today(request) - timedelta(days=limit):
                raise ValidationError(_("Corrections go back %d days. For anything older, ask HR to "
                                        "enter it directly.", limit))

    def _open_attendance(self):
        """The attendance this request is meant to close.

        Somebody who forgot to check out left one running; that record is
        the target of the correction, not something standing in its way.
        """
        self.ensure_one()
        if self.kind != 'check_out' or not self.check_out:
            return self.env['hr.attendance']
        return self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('check_out', '=', False),
            ('check_in', '<', self.check_out),
        ], order='check_in desc', limit=1)

    def _clashing_attendance(self):
        """An attendance that already covers these hours - the one being
        corrected excepted."""
        self.ensure_one()
        start = self.check_in or self.check_out
        stop = self.check_out or self.check_in
        if not start:
            return self.env['hr.attendance']
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '<=', stop),
            '|', ('check_out', '>=', start), ('check_out', '=', False),
        ]
        for attendance in (self.attendance_id | self._open_attendance()):
            domain.append(('id', '!=', attendance.id))
        return self.env['hr.attendance'].sudo().search(domain, limit=1)

    # ── the paperwork ────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fm.attendance.correction') or '/'
            # Nobody files a correction for somebody else unless they are HR.
            if not self._is_officer():
                employee = self.env.user.employee_id
                if not employee:
                    raise UserError(_("Your user is not linked to an employee, so you cannot file "
                                      "a correction. Ask HR to link it."))
                vals['employee_id'] = employee.id
                vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        locked = {'employee_id', 'date', 'kind', 'check_in', 'check_out', 'reason'}
        if locked & set(vals):
            for request in self:
                if request.state not in ('draft',) and not request._is_officer():
                    raise UserError(_("%s has already been sent. Cancel it first, or ask HR.",
                                      request.name))
        return super().write(vals)

    def unlink(self):
        for request in self:
            if request.state not in ('draft', 'cancel', 'refused'):
                raise UserError(_("%s is in the middle of its approval. Cancel it instead of "
                                  "deleting it - the trail is the point.", request.name))
        return super().unlink()

    # ── the buttons ──────────────────────────────────────────────────────
    def action_submit(self):
        for request in self:
            if not request.can_submit:
                raise AccessError(_("This is not yours to submit."))
            request._check_times()
            if request.kind == 'check_out' and not request._open_attendance():
                raise UserError(_("There is no attendance left open before %s, so there is nothing "
                                  "to close. File it as a forgotten check-in and check-out instead.",
                                  fields.Datetime.to_string(request.check_out)))
            clash = request._clashing_attendance()
            if clash:
                raise UserError(_("There is already an attendance for %(name)s covering those "
                                  "hours (%(start)s). Nothing to correct.",
                                  name=request.employee_id.name,
                                  start=fields.Datetime.to_string(clash.check_in)))
            if request.manager_user_id and request.manager_user_id != request.employee_id.sudo().user_id:
                request.sudo().write({'state': 'to_approve'})
                request._ask(request.manager_user_id,
                             _("%s asks you to approve an attendance correction.",
                               request.employee_id.name))
            else:
                # No manager with an Odoo account: straight to HR.
                request.sudo().write({'state': 'to_validate'})
                request._notify_officers()
        return True

    def action_approve(self):
        for request in self:
            if not request.can_approve:
                raise AccessError(_("Only %s or an HR officer may approve this.",
                                    request.manager_id.name or _("the manager")))
            values = {'approved_by': self.env.user.id, 'approved_on': fields.Datetime.now()}
            if request._hr_step_required():
                values['state'] = 'to_validate'
                request.sudo().write(values)
                request._notify_officers()
            else:
                request.sudo().write(values)
                request._apply()
        return True

    def action_validate(self):
        for request in self:
            if not request.can_validate:
                raise AccessError(_("Only an HR officer may validate this."))
            request.sudo().write({'validated_by': self.env.user.id,
                                  'validated_on': fields.Datetime.now()})
            request._apply()
        return True

    def action_cancel(self):
        for request in self:
            if not request.can_cancel:
                raise AccessError(_("This is not yours to cancel."))
            request.sudo().write({'state': 'cancel'})
            request.activity_unlink(['mail.mail_activity_data_todo'])
        return True

    def action_reset(self):
        for request in self:
            if not request.can_reset:
                raise AccessError(_("Only a refused or cancelled request goes back to draft."))
            request.sudo().write({'state': 'draft', 'refuse_reason': False, 'refused_by': False})
        return True

    def action_open_refuse(self):
        self.ensure_one()
        if not self.can_refuse:
            raise AccessError(_("You cannot refuse this request."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Refuse the correction"),
            'res_model': 'fm.attendance.correction.refuse',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_open_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Attendance"),
            'res_model': 'hr.attendance',
            'res_id': self.attendance_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── doing the thing ──────────────────────────────────────────────────
    def _apply(self):
        """Write the attendance. The only place this module touches hours."""
        self.ensure_one()
        clash = self._clashing_attendance()
        open_one = self._open_attendance()
        Attendance = self.env['hr.attendance'].sudo()
        if open_one:
            # The usual missed check-out: the open attendance gets its end.
            open_one.write({'check_out': self.check_out})
            attendance = open_one
        elif clash:
            raise UserError(_("An attendance already covers those hours; refuse this request or "
                              "fix the attendance by hand."))
        else:
            values = {'employee_id': self.employee_id.id, 'check_in': self.check_in or self.check_out}
            if self.check_out and self.kind != 'check_in':
                values['check_out'] = self.check_out
            elif self.check_in:
                values['check_out'] = self._closing_time()
            attendance = Attendance.create(values)
        self.sudo().write({'state': 'done', 'attendance_id': attendance.id})
        attendance.message_post(body=_(
            "Entered from attendance correction %(ref)s, approved by %(who)s.",
            ref=self.name, who=(self.validated_by or self.approved_by or self.env.user).name)) \
            if hasattr(attendance, 'message_post') else None
        self.activity_unlink(['mail.mail_activity_data_todo'])
        self._tell_employee()
        return attendance

    def _closing_time(self):
        """When a forgotten check-in has no check-out: the end of that day's
        schedule, or the next attendance if it starts earlier, or nothing at
        all when the day is still running - so the employee can clock out
        normally."""
        self.ensure_one()
        _start, scheduled_stop = self._scheduled_day()
        following = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>', self.check_in),
        ], order='check_in asc', limit=1)
        candidates = [value for value in (scheduled_stop, following.check_in) if value]
        if not candidates:
            return False
        closing = min(candidates)
        if closing <= self.check_in:
            return False
        if closing > fields.Datetime.now():
            # Still today, still working: leave it open.
            return False
        return closing

    # ── telling people ───────────────────────────────────────────────────
    def _ask(self, user, summary):
        self.ensure_one()
        if not user:
            return
        try:
            self.sudo().activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id, summary=summary,
                date_deadline=fields.Date.context_today(self))
        except Exception:  # noqa: BLE001 - a missing email must not block the request
            self.sudo().message_post(body=summary)

    def _officers(self):
        group = self.env.ref(OFFICER_GROUP, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        users = group.sudo().users if 'users' in group._fields else group.sudo().user_ids
        return users.filtered(lambda user: user.active and not user.share)

    def _notify_officers(self):
        self.ensure_one()
        officers = self._officers()
        if not officers:
            self.sudo().message_post(body=_(
                "Nobody holds the HR officer access yet, so this request is waiting. "
                "Give somebody Attendance Correction / Officer."))
            return
        for officer in officers[:5]:
            self._ask(officer, _("%s: an attendance correction needs HR.", self.employee_id.name))

    def _tell_employee(self):
        self.ensure_one()
        user = self.employee_id.sudo().user_id
        if not user:
            return
        self.sudo().message_post(
            body=_("Your attendance for %s has been corrected.", self.date),
            partner_ids=user.partner_id.ids)
