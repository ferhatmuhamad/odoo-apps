# -*- coding: utf-8 -*-
"""Where an employee may check in, and what happens when they are not there.

Every check-in and check-out Odoo records - from the systray button, the
kiosk in manual mode, and the kiosk with a barcode - ends in one method,
`_attendance_action_change`. That is the only place this module enforces
anything, so nothing the browser does can get around it.
"""

import json
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from . import geo

# How long a reason given in the browser stays valid before the check-in that
# uses it. Long enough for a slow GPS fix, short enough that a reason typed
# this morning cannot attach itself to an unrelated check-in this afternoon.
PENDING_VALIDITY = timedelta(minutes=5)


def fmt_distance(metres):
    if metres is None:
        return '-'
    if metres < 1000:
        return _('%s m') % int(round(metres))
    return _('%s km') % ('%.1f' % (metres / 1000.0))


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    fm_geo_extra_location_ids = fields.Many2many(
        'hr.work.location', 'fm_geo_employee_location_rel', 'employee_id', 'location_id',
        string='Also allowed at', groups='hr.group_hr_user',
        domain="[('fm_geo_enabled', '=', True)]",
        help='Locations besides the work location where this employee may check in. '
             'A check-in inside any allowed location counts as In Area.')
    fm_geo_exempt = fields.Boolean(
        string='Exempt from geofence', groups='hr.group_hr_user',
        help='Never flag, ask, or block this employee, wherever they check in. '
             'For people whose work is not at a fixed address.')
    # What the browser told us just before the check-in it is about to make:
    # a reason, and the GPS accuracy / speed / age that Odoo itself does not
    # send. Consumed by the very next check-in or check-out, then cleared.
    fm_geo_pending = fields.Json(string='Pending geofence data', groups='base.group_system')

    # ── Fences ───────────────────────────────────────────────────────────

    def _fm_geo_fences(self):
        """Enabled geofences this employee may use, primary first."""
        self.ensure_one()
        locations = self.work_location_id + self.fm_geo_extra_location_ids
        return locations.filtered('fm_geo_enabled')

    def _fm_geo_evaluate(self, lat, lng):
        """Judge one position against this employee's fences.

        Returns a dict with:
          status    False when no fence applies to this employee at all;
                    otherwise 'exempt', 'unknown' (no usable position),
                    'in' or 'out'.
          location  the fence the verdict is about: the one the employee is
                    inside, or failing that the one whose EDGE is nearest.
                    Nearest edge, not nearest centre - a person 400 m inside
                    a 500 m fence is not "closer" to a 100 m fence 300 m away.
          distance  metres to that fence's centre, or None.
          policy    what to enforce, or None when there is nothing to enforce.
        """
        self.ensure_one()
        fences = self._fm_geo_fences()
        verdict = {'status': False, 'location': fences.browse(), 'distance': None, 'policy': None}
        if not fences:
            return verdict
        if not geo.valid(lat, lng):
            # Nothing to measure. The primary location decides what to do
            # about a check-in with no position.
            verdict.update(status='unknown', location=fences[0], policy=fences[0].fm_geo_policy)
        else:
            by_edge = sorted(
                ((f._fm_geo_distance_to(lat, lng), f) for f in fences),
                key=lambda pair: pair[0] - pair[1].fm_geo_radius)
            distance, fence = by_edge[0]
            inside = distance <= fence.fm_geo_radius
            verdict.update(
                status='in' if inside else 'out', location=fence, distance=distance,
                policy=None if inside else fence.fm_geo_policy)
        if self.fm_geo_exempt:
            verdict.update(status='exempt', policy=None)
        return verdict

    def _fm_geo_enforce(self, verdict, mode, reason=None):
        """Turn a verdict into a decision: 'ok', 'reason' or 'block'.

        The kiosk is a shared device standing where HR put it, with no way to
        ask one person for a sentence of text. So at a kiosk the "ask for a
        reason" policy records and flags instead, and "block" only bites when
        the kiosk actually has a position to judge - a tablet without GPS must
        not lock the front door.
        """
        self.ensure_one()
        status, policy, fence = verdict['status'], verdict['policy'], verdict['location']
        decision = {'action': 'ok', 'message': '', 'note': ''}
        if not policy or policy == 'record':
            return decision

        where = fmt_distance(verdict['distance'])
        if policy == 'block':
            if status == 'out':
                decision.update(action='block', message=_(
                    'You are %(distance)s from %(location)s, outside its %(radius)s m area. '
                    'Check-ins from outside are not allowed there.',
                    distance=where, location=fence.name, radius=fence.fm_geo_radius))
            elif status == 'unknown' and mode != 'kiosk':
                decision.update(action='block', message=_(
                    'Your location could not be determined, and %(location)s does not '
                    'allow check-ins without one. Allow location access in your browser '
                    'and try again.', location=fence.name))
            else:
                decision['note'] = _('Position unavailable at the kiosk; not enforced.')
            return decision

        # policy == 'reason'
        if mode == 'kiosk':
            decision['note'] = _('Reason not collected at the kiosk.')
            return decision
        if reason:
            return decision
        if status == 'out':
            decision.update(action='reason', message=_(
                'You are %(distance)s from %(location)s, outside its %(radius)s m area. '
                'Please give a reason.',
                distance=where, location=fence.name, radius=fence.fm_geo_radius))
        else:
            decision.update(action='reason', message=_(
                'Your location could not be determined. Please give a reason for '
                'checking in without one.'))
        return decision

    # ── Pending data from the browser ────────────────────────────────────

    @api.model
    def fm_geo_precheck(self, latitude=False, longitude=False, accuracy=None,
                        speed=None, position_time=None, reason=None):
        """Called by the systray just before it makes the real check-in.

        Deliberately an @api.model method that looks up the CALLER's employee:
        a client cannot ask about, or leave a reason for, anyone else. The
        answer is advisory - the check-in itself is judged again server side.
        """
        employee = self.env.user.employee_id.sudo()
        if not employee:
            return {'action': 'ok'}
        verdict = employee._fm_geo_evaluate(latitude, longitude)
        decision = employee._fm_geo_enforce(verdict, mode='systray', reason=reason)
        if decision['action'] == 'ok':
            employee.fm_geo_pending = {
                'reason': (reason or '').strip() or None,
                'accuracy': accuracy,
                'speed': speed,
                'position_time': position_time,
                'at': fields.Datetime.now().isoformat(),
            }
        return {'action': decision['action'], 'message': decision['message']}

    def _fm_geo_take_pending(self):
        """Read and clear what the browser left, if it is still fresh."""
        self.ensure_one()
        data = self.fm_geo_pending or {}
        if data:
            self.fm_geo_pending = False
        try:
            left_at = fields.Datetime.from_string(data.get('at', '').replace('T', ' ')[:19])
        except (ValueError, AttributeError):
            return {}
        if not left_at or fields.Datetime.now() - left_at > PENDING_VALIDITY:
            return {}
        return data

    # ── The one enforcement point ────────────────────────────────────────

    def _attendance_action_change(self, geo_information=None):
        self.ensure_one()
        info = geo_information or {}
        mode = info.get('mode')
        side = 'in' if self.attendance_state != 'checked_in' else 'out'
        employee = self.sudo()
        lat, lng = info.get('latitude'), info.get('longitude')

        if mode:
            verdict = employee._fm_geo_evaluate(lat, lng)
            pending = employee._fm_geo_take_pending()
            decision = employee._fm_geo_enforce(verdict, mode, reason=pending.get('reason'))
            if decision['action'] == 'block':
                raise UserError(decision['message'])
            if decision['action'] == 'reason':
                raise UserError(_(
                    'A reason is required to check in from outside %(location)s.',
                    location=verdict['location'].name))
        else:
            # No mode means nobody pressed a button: a test, a script, a
            # migration. There is no position to judge and nobody to ask.
            verdict, pending, decision = None, {}, None

        attendance = super()._attendance_action_change(geo_information)

        if verdict and verdict['status']:
            attendance.sudo()._fm_geo_store(side, verdict, pending, decision['note'])
        return attendance
