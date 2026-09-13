# -*- coding: utf-8 -*-
"""The board: one salesperson at a time, on a screen on the wall.

Everything is a cohort of the lead's CREATION date - the month it came in
(yearly view) or the day it came in (monthly view) - split into Won, Lost
and In progress from one and the same query, so by construction
`leads in = won + lost + in progress`; two numbers on the screen can never
disagree. Closed value is the exception and says so: it follows the date
the deal was closed, because that is when the money became real.

Lost leads are archived by Odoo. Every query here that counts leads reads
archived ones too; the one that counts revenue insists on active leads,
because a deal that reached a won stage and was then marked lost is not
revenue, whatever its stage still says.

All lead data is read with sudo: the board is meant for a screen, or a
user whose job is to look at it, not to be a CRM user. Access to the page
is a group; opening a list from it needs real CRM read rights.
"""

import base64
import calendar
from collections import defaultdict
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

PARAM = 'fm_sales_scoreboard.'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

LEAD_KINDS = {
    'created': 'Leads in',
    'created_won': 'Won',
    'created_lost': 'Lost',
    'created_open': 'In progress',
    'won_closed': 'Closed',
    'kpi_created': 'Leads this month',
    'kpi_won': 'Won this month',
    'pipeline': 'Open opportunities',
}


class SalesScoreboard(models.AbstractModel):
    _name = 'fm.sales.scoreboard'
    _description = 'Sales Scoreboard'

    # ── Settings ─────────────────────────────────────────────────────────

    @api.model
    def _config(self):
        icp = self.env['ir.config_parameter'].sudo()

        def integer(key, default, floor=1):
            try:
                return max(floor, int(icp.get_param(PARAM + key) or default))
            except (TypeError, ValueError):
                return default

        def number(key, default):
            try:
                return max(0.0, float(icp.get_param(PARAM + key) or default))
            except (TypeError, ValueError):
                return default

        def ids(key):
            raw = icp.get_param(PARAM + key) or ''
            return [int(x) for x in raw.split(',') if x.strip().isdigit()]

        return {
            'refresh_seconds': integer('refresh_seconds', 15, 5),
            'slide_seconds': integer('slide_seconds', 10, 3),
            'won_stage_ids': ids('won_stage_ids'),
            'user_ids': ids('user_ids'),
            'creator_ids': ids('creator_ids'),
            'target': number('target', 0.0),
        }

    def _won_stage_ids(self, config):
        if config['won_stage_ids']:
            return set(config['won_stage_ids'])
        return set(self.env['crm.stage'].sudo().search([('is_won', '=', True)]).ids)

    # ── Who is on the board ──────────────────────────────────────────────

    def _salespersons(self, config):
        """Users who actually own leads in the current companies - not team
        members, who in real life are often not the people selling. Unless
        an administrator listed exactly who belongs on the board."""
        companies = self.env.companies.ids
        Lead = self.env['crm.lead'].sudo().with_context(active_test=False)
        if config['user_ids']:
            user_ids = config['user_ids']
        else:
            user_ids = [u.id for (u,) in Lead._read_group(
                [('user_id', '!=', False), ('company_id', 'in', companies)], ['user_id'])]
            if not user_ids:
                teams = self.env['crm.team'].sudo().search([('company_id', 'in', [False] + companies)])
                user_ids = (teams.member_ids | teams.user_id).ids
        users = self.env['res.users'].sudo().browse(user_ids).exists()
        return users.filtered(lambda u: u.active and not u.share).sorted('name')

    def _team_of(self, user):
        return user.sale_team_id

    def _employees(self, users):
        emps = self.env['hr.employee'].sudo().with_context(active_test=False).search(
            [('user_id', 'in', users.ids)], order='active desc, id')
        by_user = {}
        for emp in emps:
            by_user.setdefault(emp.user_id.id, emp)
        return by_user

    # ── Periods ──────────────────────────────────────────────────────────

    @staticmethod
    def _bounds(mode, year, month):
        if mode == 'day':
            days = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, days), [str(d) for d in range(1, days + 1)]
        return date(year, 1, 1), date(year, 12, 31), list(MONTHS)

    @staticmethod
    def _dt(d, end=False):
        return datetime.combine(d, datetime.max.time() if end else datetime.min.time())

    @staticmethod
    def _bucket(mode, dt, month):
        if isinstance(dt, datetime):
            dt = dt.date()
        if mode == 'day':
            return dt.day - 1 if dt.month == month else None
        return dt.month - 1

    # ── Money per lead: expected revenue, else the confirmed order ───────

    def _amounts(self, lead_rows):
        """{lead_id: value}. A lead whose expected revenue is zero may still
        have a confirmed order behind it; that order's total is used."""
        amounts = {r['id']: r['expected_revenue'] or 0.0 for r in lead_rows}
        missing = [lid for lid, v in amounts.items() if not v]
        if missing:
            for opp, total in self.env['sale.order'].sudo()._read_group(
                    [('opportunity_id', 'in', missing), ('state', '=', 'sale')],
                    ['opportunity_id'], ['amount_total:sum']):
                amounts[opp.id] = total or 0.0
        return amounts

    # ── The board ────────────────────────────────────────────────────────

    @api.model
    def get_data(self, mode='month', year=None, month=None, team_id=None, creator_id=None):
        if not (self.env.user.has_group('fm_sales_scoreboard.group_scoreboard') or self.env.user._is_admin()):
            raise AccessError(_('You are not allowed to see the sales scoreboard.'))
        today = fields.Date.context_today(self)
        year = int(year) if year else today.year
        month = int(month) if month else today.month
        mode = 'day' if mode == 'day' else 'month'
        creator_id = int(creator_id) if creator_id else False
        config = self._config()
        companies = self.env.companies.ids
        won_ids = self._won_stage_ids(config)
        start, end, labels = self._bounds(mode, year, month)
        n = len(labels)
        m_start = date(year, month, 1)
        m_end = date(year, month, calendar.monthrange(year, month)[1])

        users = self._salespersons(config)
        employees = self._employees(users)
        filters = self._filters(users, companies, config)

        # Filter by team: who is on the board.
        if team_id == 'none':
            users = users.filtered(lambda u: not self._team_of(u))
        elif team_id:
            users = users.filtered(lambda u: self._team_of(u).id == int(team_id))

        # One pass over the leads for everybody on the board, then split.
        Lead = self.env['crm.lead'].sudo().with_context(active_test=False)
        base = [('user_id', 'in', users.ids), ('company_id', 'in', companies)]
        if creator_id:
            base.append(('create_uid', '=', creator_id))
        fields_ = ['user_id', 'create_date', 'date_closed', 'stage_id', 'active', 'expected_revenue', 'probability', 'type']
        rows = Lead.search_read(base + [
            '|', '&', ('create_date', '>=', self._dt(min(start, m_start))), ('create_date', '<=', self._dt(max(end, m_end), True)),
            '&', ('date_closed', '>=', self._dt(min(start, m_start))), ('date_closed', '<=', self._dt(max(end, m_end), True)),
        ], fields_)
        open_rows = Lead.search_read(base + [
            ('type', '=', 'opportunity'), ('active', '=', True), ('stage_id.is_won', '=', False),
        ], ['user_id', 'expected_revenue', 'probability'])
        amounts = self._amounts(rows)

        by_user = defaultdict(list)
        for r in rows:
            by_user[r['user_id'][0]].append(r)
        open_by_user = defaultdict(list)
        for r in open_rows:
            open_by_user[r['user_id'][0]].append(r)

        def in_period(dt, a, b):
            return dt and self._dt(a) <= fields.Datetime.to_datetime(dt) <= self._dt(b, True)

        def is_won(r):
            return r['active'] and r['stage_id'] and r['stage_id'][0] in won_ids

        target = config['target']
        board = []
        for user in users:
            leads = by_user.get(user.id, [])
            series = {k: [0] * n for k in ('leads', 'won', 'lost', 'open')}
            values = {k: [0.0] * n for k in ('leads', 'won', 'lost', 'open')}
            for r in leads:
                if not in_period(r['create_date'], start, end):
                    continue
                idx = self._bucket(mode, fields.Datetime.to_datetime(r['create_date']), month)
                if idx is None:
                    continue
                kind = 'lost' if not r['active'] else ('won' if is_won(r) else 'open')
                v = amounts.get(r['id'], 0.0)
                series['leads'][idx] += 1
                values['leads'][idx] += v
                series[kind][idx] += 1
                values[kind][idx] += v
            closed = [r for r in leads if is_won(r) and in_period(r['date_closed'], start, end)]
            closed_value = sum(amounts.get(r['id'], 0.0) for r in closed)
            m_created = [r for r in leads if in_period(r['create_date'], m_start, m_end)]
            m_won = [r for r in leads if is_won(r) and in_period(r['date_closed'], m_start, m_end)]
            m_revenue = sum(amounts.get(r['id'], 0.0) for r in m_won)
            opps = open_by_user.get(user.id, [])
            pipeline = sum(o['expected_revenue'] or 0.0 for o in opps)
            weighted = sum((o['expected_revenue'] or 0.0) * (o['probability'] or 0.0) / 100.0 for o in opps)
            emp = employees.get(user.id)
            board.append({
                'user_id': user.id,
                'name': user.name,
                'team': self._team_of(user).name or '',
                'job_title': (emp.job_title or (emp.job_id.name if emp.job_id else '')) if emp else '',
                'department': emp.department_id.name if emp and emp.department_id else '',
                'since': emp.create_date.strftime('%b %Y') if emp and emp.create_date else '',
                'phone': (emp and (emp.mobile_phone or emp.work_phone)) or user.partner_id.phone or '',
                'email': user.email or (emp and emp.work_email) or '',
                'avatar': self._avatar(emp, user),
                'series': series,
                'values': values,
                'summary': {
                    'leads': sum(series['leads']), 'won': sum(series['won']),
                    'lost': sum(series['lost']), 'open': sum(series['open']),
                    'leads_value': sum(values['leads']), 'won_value': sum(values['won']),
                    'lost_value': sum(values['lost']), 'open_value': sum(values['open']),
                    'closed_count': len(closed), 'closed_value': closed_value,
                    'month_created': len(m_created), 'month_won': len(m_won),
                    'month_revenue': m_revenue,
                    'conversion': round(len(m_won) * 100.0 / len(m_created), 1) if m_created else 0.0,
                    'target': target,
                    'achievement': round(m_revenue * 100.0 / target, 1) if target else None,
                    'pipeline_count': len(opps), 'pipeline_value': pipeline,
                    'pipeline_weighted': round(weighted),
                },
            })

        currency = self.env.company.currency_id
        days_in_month = calendar.monthrange(year, month)[1]
        return {
            'config': {'refresh_seconds': config['refresh_seconds'], 'slide_seconds': config['slide_seconds']},
            'mode': mode, 'year': year, 'month': month,
            'labels': labels,
            'years': list(range(year - 3, year + 1)),
            'months': MONTHS,
            'filters': dict(filters, team_id=team_id or False, creator_id=creator_id or False),
            'company': self.env.company.name,
            'kpi_month': '%s %s' % (MONTHS[month - 1], year),
            'period_label': ('%s %s' % (MONTHS[month - 1], year)) if mode == 'day' else str(year),
            'target': target,
            'target_line': (target / days_in_month) if mode == 'day' else target,
            'currency_symbol': currency.symbol or '',
            'currency_position': currency.position,
            'salespersons': board,
        }

    def _avatar(self, emp, user):
        """The picture, as data: the viewer may have no right to read
        hr.employee, and a board without faces is a spreadsheet."""
        rec = emp if emp and emp.avatar_256 else user
        data = rec.avatar_256 if rec else False
        if not data:
            return ''
        return 'data:image/png;base64,' + (data.decode() if isinstance(data, bytes) else data)

    def _filters(self, users, companies, config):
        teams = self.env['crm.team'].sudo().search([('company_id', 'in', [False] + companies)])
        creators = self.env['res.users'].sudo().browse(config['creator_ids']).exists() if config['creator_ids'] else \
            self.env['res.users'].sudo().browse([u.id for (u,) in self.env['crm.lead'].sudo().with_context(active_test=False)._read_group(
                [('company_id', 'in', companies), ('create_uid', '!=', False)], ['create_uid'])]).exists()
        return {
            'teams': [{'id': t.id, 'name': t.name} for t in teams],
            'has_teamless': any(not self._team_of(u) for u in users),
            'creators': [{'id': u.id, 'name': u.name} for u in creators.sorted('name')],
        }

    # ── Click-through ────────────────────────────────────────────────────

    @api.model
    def get_lead_action(self, user_id, kind, mode='month', year=None, month=None, bucket=None, creator_id=None):
        if not self.env['crm.lead'].check_access_rights('read', raise_exception=False):
            raise AccessError(_('You have no access to CRM, so the leads behind this figure cannot be opened.'))
        if kind not in LEAD_KINDS:
            raise UserError(_('Unknown figure: %s', kind))
        today = fields.Date.context_today(self)
        year = int(year) if year else today.year
        month = int(month) if month else today.month
        mode = 'day' if mode == 'day' else 'month'
        bucket = None if bucket in (None, '') else int(bucket)
        won_ids = list(self._won_stage_ids(self._config()))
        user = self.env['res.users'].sudo().browse(int(user_id)).exists()
        if not user:
            raise UserError(_('Salesperson not found.'))
        base = [('user_id', '=', user.id), ('company_id', 'in', self.env.companies.ids)]
        if creator_id:
            base.append(('create_uid', '=', int(creator_id)))

        if kind in ('kpi_created', 'kpi_won'):
            start, end = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
            label = '%s %s' % (MONTHS[month - 1], year)
        elif bucket is None:
            start, end, _labels = self._bounds(mode, year, month)
            label = ('%s %s' % (MONTHS[month - 1], year)) if mode == 'day' else str(year)
        elif mode == 'day':
            day = min(max(bucket + 1, 1), calendar.monthrange(year, month)[1])
            start = end = date(year, month, day)
            label = '%s %s %s' % (day, MONTHS[month - 1], year)
        else:
            m = min(max(bucket + 1, 1), 12)
            start, end = date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1])
            label = '%s %s' % (MONTHS[m - 1], year)

        if kind == 'pipeline':
            domain = base + [('type', '=', 'opportunity'), ('active', '=', True), ('stage_id.is_won', '=', False)]
            label = _('now')
        elif kind in ('won_closed', 'kpi_won'):
            domain = base + [('stage_id', 'in', won_ids), ('active', '=', True),
                             ('date_closed', '>=', self._dt(start)), ('date_closed', '<=', self._dt(end, True))]
        else:
            domain = base + [('create_date', '>=', self._dt(start)), ('create_date', '<=', self._dt(end, True))]
            if kind == 'created_won':
                domain += [('stage_id', 'in', won_ids), ('active', '=', True)]
            elif kind == 'created_lost':
                domain += [('active', '=', False)]
            elif kind == 'created_open':
                domain += [('stage_id', 'not in', won_ids), ('active', '=', True)]
        return {
            'type': 'ir.actions.act_window',
            'name': '%s · %s · %s' % (user.name, LEAD_KINDS[kind], label),
            'res_model': 'crm.lead',
            'views': [[False, 'list'], [False, 'kanban'], [False, 'form']],
            'domain': domain,
            'context': {'active_test': False, 'create': False},
            'target': 'current',
        }
