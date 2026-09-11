# -*- coding: utf-8 -*-
"""What the geofence concluded about each check-in and check-out.

Everything here is a RECORD of a verdict, including a snapshot of the circle
it was judged against. Verdicts are facts about the past; moving a pin or
widening a radius later must not quietly change them. HR can re-run the
judgement on purpose with "Evaluate geofence".
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _

from . import geo

STATUSES = [
    ('in', 'In area'),
    ('out', 'Out of area'),
    ('unknown', 'No position'),
    ('exempt', 'Exempt'),
]

SIDES = ('in', 'out')


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # ── Check-in ─────────────────────────────────────────────────────────
    in_fm_geo_status = fields.Selection(STATUSES, string='Area', readonly=True, copy=False)
    in_fm_geo_location_id = fields.Many2one(
        'hr.work.location', string='Location', readonly=True, copy=False, ondelete='set null')
    in_fm_geo_distance = fields.Float(string='Distance (m)', readonly=True, copy=False, digits=(12, 1))
    in_fm_geo_fence = fields.Json(readonly=True, copy=False)
    in_fm_geo_reason = fields.Text(string='Reason', readonly=True, copy=False)
    in_fm_geo_flagged = fields.Boolean(string='GPS flagged', readonly=True, copy=False)
    in_fm_geo_note = fields.Char(string='Note', readonly=True, copy=False)

    # ── Check-out ────────────────────────────────────────────────────────
    out_fm_geo_status = fields.Selection(STATUSES, string='Area (out)', readonly=True, copy=False)
    out_fm_geo_location_id = fields.Many2one(
        'hr.work.location', string='Location (out)', readonly=True, copy=False, ondelete='set null')
    out_fm_geo_distance = fields.Float(string='Distance (m, out)', readonly=True, copy=False, digits=(12, 1))
    out_fm_geo_fence = fields.Json(readonly=True, copy=False)
    out_fm_geo_reason = fields.Text(string='Reason (out)', readonly=True, copy=False)
    out_fm_geo_flagged = fields.Boolean(string='GPS flagged (out)', readonly=True, copy=False)
    out_fm_geo_note = fields.Char(string='Note (out)', readonly=True, copy=False)

    # One flag to filter on: either end of the attendance looked wrong.
    fm_geo_flagged = fields.Boolean(
        string='Flagged', compute='_compute_fm_geo_flagged', store=True)

    @api.depends('in_fm_geo_flagged', 'out_fm_geo_flagged')
    def _compute_fm_geo_flagged(self):
        for att in self:
            att.fm_geo_flagged = att.in_fm_geo_flagged or att.out_fm_geo_flagged

    # ── Storing a verdict ────────────────────────────────────────────────

    def _fm_geo_store(self, side, verdict, pending=None, note=''):
        """Write one side's verdict, plus what the GPS data looked like."""
        self.ensure_one()
        pending = pending or {}
        lat = self[side + '_latitude']
        lng = self[side + '_longitude']
        when = self.check_out if side == 'out' else self.check_in
        flagged, reasons = self._fm_geo_suspicion(lat, lng, when, pending)
        notes = [n for n in [note] + reasons if n]
        fence = verdict['location']
        self.write({
            side + '_fm_geo_status': verdict['status'],
            side + '_fm_geo_location_id': fence.id,
            side + '_fm_geo_distance': verdict['distance'],
            side + '_fm_geo_fence': fence._fm_geo_fence_snapshot() if fence else False,
            side + '_fm_geo_reason': pending.get('reason') or False,
            side + '_fm_geo_flagged': flagged,
            side + '_fm_geo_note': ' '.join(notes) or False,
        })

    def action_fm_geo_evaluate(self):
        """Judge (again) from the stored coordinates and today's fences.

        For HR, after moving a pin or on a database that already had
        attendances when this module was installed. A reason that was given
        is kept; it belongs to the person, not to the circle.
        """
        for att in self:
            employee = att.employee_id.sudo()
            for side in SIDES:
                if side == 'out' and not att.check_out:
                    continue
                if att[side + '_mode'] == 'manual':
                    # Entered by hand in the backend: no device, no position,
                    # and nothing an HR officer typed in should be flagged.
                    continue
                verdict = employee._fm_geo_evaluate(att[side + '_latitude'], att[side + '_longitude'])
                if not verdict['status']:
                    continue
                att.sudo()._fm_geo_store(
                    side, verdict, {'reason': att[side + '_fm_geo_reason']},
                    note=_('Evaluated again on %s.') % fields.Date.context_today(self))
        return True

    # ── Does this position look real? ────────────────────────────────────

    @api.model
    def _fm_geo_thresholds(self):
        icp = self.env['ir.config_parameter'].sudo()

        def num(key, default):
            try:
                return float(icp.get_param(key) or default)
            except ValueError:
                return default

        return {
            'max_accuracy': num('fm_attendance_geo.max_accuracy', 500.0),
            'max_age_min': num('fm_attendance_geo.max_age_min', 5.0),
            'max_speed_kmh': num('fm_attendance_geo.max_speed_kmh', 150.0),
        }

    def _fm_geo_suspicion(self, lat, lng, when, pending):
        """Flag a position the way a careful HR officer would: not an
        accusation, a reason to look twice. Returns (flagged, [notes]).

        Two kinds of evidence. What the device said about itself - accuracy,
        speed, the age of the fix - which Odoo does not normally send and
        which the systray patch adds. And what the server can work out alone:
        how fast the employee would have had to travel from wherever they last
        checked in or out. The second one needs no cooperation from the
        device, which is the point.
        """
        self.ensure_one()
        t = self._fm_geo_thresholds()
        notes = []

        accuracy = pending.get('accuracy')
        if accuracy is not None:
            try:
                accuracy = float(accuracy)
            except (TypeError, ValueError):
                accuracy = None
        if accuracy is not None:
            if accuracy <= 0:
                notes.append(_('The device reported an accuracy of 0 m, which real GPS hardware never does.'))
            elif accuracy > t['max_accuracy']:
                notes.append(_('Low accuracy: within %s m.') % int(accuracy))

        speed = pending.get('speed')
        if speed not in (None, False):
            try:
                kmh = float(speed) * 3.6
                if kmh > t['max_speed_kmh']:
                    notes.append(_('The device reported moving at %s km/h.') % int(kmh))
            except (TypeError, ValueError):
                pass

        pos_time = pending.get('position_time')
        if pos_time and when:
            try:
                # Epoch milliseconds, as the browser's Geolocation API gives it.
                fixed_at = datetime.utcfromtimestamp(float(pos_time) / 1000.0)
                age = (when - fixed_at).total_seconds() / 60.0
                if age > t['max_age_min']:
                    notes.append(_('The position was %s minutes old when it was sent.') % int(age))
            except (TypeError, ValueError, OverflowError, OSError):
                pass

        if geo.valid(lat, lng) and when:
            previous = self._fm_geo_previous_point(when)
            if previous:
                p_lat, p_lng, p_when, p_label = previous
                hours = (when - p_when).total_seconds() / 3600.0
                if hours > 0:
                    km = geo.distance_m(lat, lng, p_lat, p_lng) / 1000.0
                    kmh = km / hours
                    if kmh > t['max_speed_kmh']:
                        notes.append(_(
                            '%(km)s km from the previous %(label)s %(minutes)s minutes earlier, '
                            'which is %(kmh)s km/h.',
                            km='%.1f' % km, label=p_label,
                            minutes=int(hours * 60), kmh=int(kmh)))
        return bool(notes), notes

    def _fm_geo_previous_point(self, before):
        """The employee's most recent known position before `before`:
        (lat, lng, when, label) or None."""
        self.ensure_one()
        # The check-out of this very record is judged against its own
        # check-in first: 8:00 at the office and 8:05 a hundred kilometres
        # away is the clearest case there is.
        if self.check_in and self.check_in < before and geo.valid(self.in_latitude, self.in_longitude):
            return self.in_latitude, self.in_longitude, self.check_in, _('check-in')
        domain = [('employee_id', '=', self.employee_id.id), ('id', '!=', self.id),
                  ('check_in', '<', before)]
        for att in self.sudo().search(domain, order='check_in desc', limit=5):
            if att.check_out and att.check_out < before and geo.valid(att.out_latitude, att.out_longitude):
                return att.out_latitude, att.out_longitude, att.check_out, _('check-out')
            if geo.valid(att.in_latitude, att.in_longitude):
                return att.in_latitude, att.in_longitude, att.check_in, _('check-in')
        return None

    # ── Map configuration for the browser ────────────────────────────────

    @api.model
    def fm_geo_map_config(self):
        """Tile server and attribution. Read with sudo because the settings
        live in ir.config_parameter, which ordinary users cannot read, and
        every employee's attendance form has a map on it."""
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'tile_url': icp.get_param('fm_attendance_geo.tile_url')
                        or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            'attribution': icp.get_param('fm_attendance_geo.tile_attribution')
                           or '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }

    # ── Data for the map of a day ────────────────────────────────────────

    @api.model
    def fm_geo_map_data(self, day=None):
        """Every fence, and every check-in of one day, for the day map.

        The day is the USER's day: check-ins are stored in UTC, and an officer
        in Jakarta asking for "today" means midnight to midnight in Jakarta.
        """
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        day = fields.Date.from_string(day) if day else fields.Date.context_today(self)
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end = start + timedelta(days=1)

        fences = self.env['hr.work.location'].search([
            ('fm_geo_enabled', '=', True),
            ('company_id', 'in', self.env.companies.ids),
        ])
        attendances = self.search([
            ('check_in', '>=', start), ('check_in', '<', end),
            ('employee_id.company_id', 'in', self.env.companies.ids),
        ], order='check_in')

        points = []
        for att in attendances:
            if not geo.valid(att.in_latitude, att.in_longitude):
                continue
            points.append({
                'id': att.id,
                'employee_id': att.employee_id.id,
                'employee': att.employee_id.name,
                'check_in': fields.Datetime.context_timestamp(self, att.check_in).strftime('%H:%M'),
                'lat': att.in_latitude,
                'lng': att.in_longitude,
                'status': att.in_fm_geo_status or 'none',
                'distance': att.in_fm_geo_distance,
                'location': att.in_fm_geo_location_id.name or '',
                'flagged': att.in_fm_geo_flagged,
                'note': att.in_fm_geo_note or '',
                'reason': att.in_fm_geo_reason or '',
                'mode': att.in_mode or '',
            })
        counted = [a for a in attendances if a.in_fm_geo_status]
        return {
            'day': fields.Date.to_string(day),
            'fences': [{
                'id': f.id, 'name': f.name, 'lat': f.fm_geo_latitude, 'lng': f.fm_geo_longitude,
                'radius': f.fm_geo_radius, 'policy': f.fm_geo_policy,
            } for f in fences],
            'points': points,
            'summary': {
                'total': len(attendances),
                'positioned': len(points),
                'in': sum(1 for a in counted if a.in_fm_geo_status == 'in'),
                'out': sum(1 for a in counted if a.in_fm_geo_status == 'out'),
                'unknown': sum(1 for a in counted if a.in_fm_geo_status == 'unknown'),
                'flagged': sum(1 for a in attendances if a.in_fm_geo_flagged),
            },
        }
