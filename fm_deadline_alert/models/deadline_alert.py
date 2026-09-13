# -*- coding: utf-8 -*-
"""What the bell shows: everything of mine that is due soon or overdue.

Two kinds of thing, one list. Activities assigned to me - the scheduled
"call back", "review", "approve" - and records whose own deadline field
is mine: tasks, quotations, invoices, whatever the sources say. Both are
judged against the same window (24 hours by default), and both open the
record when clicked.
"""

from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

PARAM = 'fm_deadline_alert.'
BUS_TYPE = 'fm_deadline_alert/refresh'


class DeadlineAlert(models.AbstractModel):
    _name = 'fm.deadline.alert'
    _description = 'Deadline Alerts'

    @api.model
    def _window_hours(self):
        try:
            return max(1, int(self.env['ir.config_parameter'].sudo().get_param(PARAM + 'window_hours') or 24))
        except ValueError:
            return 24

    @api.model
    def _settings(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'window_hours': self._window_hours(),
            'toast': (icp.get_param(PARAM + 'toast', 'True') or 'True') == 'True',
            'poll_minutes': 5,
        }

    # ── The list ─────────────────────────────────────────────────────────

    @api.model
    def get_alerts(self):
        """Overdue first, then by deadline. Each row carries enough to be
        drawn and to be opened; nothing the client has to look up."""
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        hours = self._window_hours()
        limit_dt = now + timedelta(hours=hours)
        limit_date = fields.Datetime.context_timestamp(self, limit_dt).date()
        alerts = self._activity_alerts(today, limit_date) + self._record_alerts(today, now, limit_date, limit_dt)
        alerts.sort(key=lambda a: (0 if a['state'] == 'overdue' else 1, a['deadline'], a['title']))
        return {'alerts': alerts, 'settings': self._settings(), 'today': fields.Date.to_string(today)}

    def _state_of(self, days):
        if days < 0:
            return 'overdue'
        if days == 0:
            return 'today'
        return 'upcoming'

    def _activity_alerts(self, today, limit_date):
        activities = self.env['mail.activity'].search([
            ('user_id', '=', self.env.uid),
            ('date_deadline', '<=', limit_date),
        ], order='date_deadline asc, id asc')
        out = []
        for act in activities:
            days = (act.date_deadline - today).days
            record = self.env[act.res_model].browse(act.res_id) if act.res_model in self.env else None
            try:
                title = record.display_name if record and record.exists() else ''
            except AccessError:
                title = ''
            out.append({
                'key': 'activity-%d' % act.id,
                'kind': 'activity',
                'activity_id': act.id,
                'res_model': act.res_model,
                'res_id': act.res_id,
                'title': title or act.res_name or act.summary or act.activity_type_id.name,
                'summary': act.summary or act.activity_type_id.name or '',
                'badge': act.activity_type_id.name or _('Activity'),
                'icon': act.activity_type_id.icon or 'fa-clock-o',
                'deadline': fields.Date.to_string(act.date_deadline),
                'days': days,
                'state': self._state_of(days),
            })
        return out

    def _record_alerts(self, today, now, limit_date, limit_dt):
        out = []
        for src in self.env['fm.deadline.source'].sudo().search([]):
            model = src.model_name
            if model not in self.env or src.date_field_name not in self.env[model]._fields:
                continue
            Model = self.env[model]
            field = Model._fields[src.date_field_name]
            is_dt = field.type == 'datetime'
            domain = src._domain() + [
                (src.date_field_name, '!=', False),
                (src.date_field_name, '<=', limit_dt if is_dt else limit_date),
                (src.user_field_name, 'in', [self.env.uid]),
            ]
            try:
                # As the user: what they may not see, they are not warned about.
                records = Model.search(domain, order='%s asc' % src.date_field_name, limit=200)
            except Exception:
                continue
            for rec in records:
                value = rec[src.date_field_name]
                if is_dt:
                    local = fields.Datetime.context_timestamp(self, value)
                    days = (local.date() - today).days
                    overdue = value < now
                else:
                    days = (value - today).days
                    overdue = value < today
                out.append({
                    'key': 'record-%s-%d' % (model, rec.id),
                    'kind': 'record',
                    'activity_id': False,
                    'res_model': model,
                    'res_id': rec.id,
                    'title': rec.display_name or '',
                    'summary': '',
                    'badge': src.name,
                    'icon': src.icon or 'fa-calendar',
                    'deadline': fields.Date.to_string(local.date() if is_dt else value),
                    'days': days,
                    'state': 'overdue' if overdue else self._state_of(days),
                })
        return out

    # ── Actions from the bell ────────────────────────────────────────────

    @api.model
    def mark_activity_done(self, activity_id):
        act = self.env['mail.activity'].browse(int(activity_id)).exists()
        if act and act.user_id == self.env.user:
            act.action_done()
        return True

    # ── Bus ──────────────────────────────────────────────────────────────

    @api.model
    def _notify_users(self, users):
        """Tell these users' browsers to fetch the list again."""
        Bus = self.env['bus.bus'].sudo()
        for user in users.filtered(lambda u: u.active and not u.share):
            Bus._sendone(user.partner_id, BUS_TYPE, {})
