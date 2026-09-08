from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PublicHolidayImport(models.TransientModel):
    _name = 'fm.public.holiday.import'
    _description = 'Import Public Holidays'

    country_id = fields.Many2one(
        'res.country',
        string='Country',
        required=True,
        help="Country whose public holidays you want to add to your working schedules.",
    )
    year_from = fields.Integer(
        string='From Year',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    year_to = fields.Integer(
        string='To Year',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    calendar_ids = fields.Many2many(
        'resource.calendar',
        string='Working Schedules',
        help="Schedules that will receive the holidays. Leave empty to apply to every "
             "working schedule of the current company.",
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        default='draft',
        readonly=True,
    )

    available_count = fields.Integer(
        string='Holidays Found', compute='_compute_available', readonly=True)
    preview = fields.Text(string='Preview', compute='_compute_available', readonly=True)
    library_available = fields.Boolean(
        string='Library Installed', compute='_compute_library', readonly=True)

    created_count = fields.Integer(string='Created', readonly=True)
    skipped_count = fields.Integer(string='Already Present', readonly=True)
    calendar_count = fields.Integer(string='Schedules Updated', readonly=True)

    @api.depends_context('uid')
    def _compute_library(self):
        available = self.env['fm.public.holiday']._library_available()
        for wizard in self:
            wizard.library_available = available

    @api.depends('country_id', 'year_from', 'year_to')
    def _compute_available(self):
        for wizard in self:
            holidays = wizard._find_holidays()
            wizard.available_count = len(holidays)
            if not holidays:
                wizard.preview = False
                continue
            shown = holidays[:12]
            lines = ["%s  —  %s" % (h.date, h.name) for h in shown]
            if len(holidays) > len(shown):
                lines.append(_("… and %s more", len(holidays) - len(shown)))
            wizard.preview = "\n".join(lines)

    def _find_holidays(self):
        self.ensure_one()
        if not self.country_id or not self.year_from or not self.year_to:
            return self.env['fm.public.holiday']
        return self.env['fm.public.holiday'].search([
            ('country_id', '=', self.country_id.id),
            ('year', '>=', self.year_from),
            ('year', '<=', self.year_to),
        ], order='date')

    def _target_calendars(self):
        self.ensure_one()
        if self.calendar_ids:
            return self.calendar_ids
        return self.env['resource.calendar'].search([
            ('company_id', 'in', [False, self.env.company.id]),
        ])

    def _day_bounds_utc(self, day):
        """Return the UTC datetimes covering a full day, expressed in the
        current user's timezone.

        `hr_holidays` re-bases public holidays from the user's timezone into
        the working schedule's timezone when the record is created
        (`_prepare_public_holidays_values`). Converting with the calendar
        timezone here would apply that shift twice, so we deliberately use the
        user timezone and let Odoo do the rest.
        """
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC)
        end = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.UTC)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    def _check_years(self):
        self.ensure_one()
        if self.year_to < self.year_from:
            raise UserError(_("The last year cannot be earlier than the first year."))
        if self.year_to - self.year_from > 20:
            raise UserError(_("Please import at most 21 years at a time."))

    def action_fetch_from_library(self):
        """Pull holidays for this country from the optional `holidays` package."""
        self.ensure_one()
        self._check_years()
        if not self.country_id.code:
            raise UserError(_("The selected country has no ISO code."))
        created = self.env['fm.public.holiday']._fetch_from_library(
            self.country_id.code, self.year_from, self.year_to)
        message = (
            _("%s holiday dates added to the reference list.", created) if created
            else _("Nothing new — every date was already in the reference list.")
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if created else 'warning',
                'message': message,
                'next': self._reopen(),
            },
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        """Copy the selected holidays into the chosen working schedules."""
        self.ensure_one()
        self._check_years()

        holidays = self._find_holidays()
        if not holidays:
            raise UserError(_(
                "No holiday found for %(country)s between %(y1)s and %(y2)s.\n\n"
                "Use “Fetch from library” first if this country is not part of the "
                "bundled data.",
                country=self.country_id.name, y1=self.year_from, y2=self.year_to,
            ))

        calendars = self._target_calendars()
        if not calendars:
            raise UserError(_("There is no working schedule to add the holidays to."))

        Leave = self.env['resource.calendar.leaves']
        created = skipped = 0
        for calendar in calendars:
            # Stored datetimes are UTC; convert back to the schedule's own
            # timezone before comparing with a holiday's local date.
            tz = pytz.timezone(calendar.tz or 'UTC')
            existing = {
                pytz.UTC.localize(leave.date_from).astimezone(tz).date()
                for leave in Leave.search([
                    ('calendar_id', '=', calendar.id),
                    ('resource_id', '=', False),
                ])
                if leave.date_from
            }

            vals_list = []
            for holiday in holidays:
                if holiday.date in existing:
                    skipped += 1
                    continue
                date_from, date_to = self._day_bounds_utc(holiday.date)
                vals_list.append({
                    'name': holiday.name,
                    'calendar_id': calendar.id,
                    'company_id': calendar.company_id.id or self.env.company.id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'resource_id': False,
                    'time_type': 'leave',
                })
            if vals_list:
                Leave.create(vals_list)
                created += len(vals_list)

        self.write({
            'state': 'done',
            'created_count': created,
            'skipped_count': skipped,
            'calendar_count': len(calendars),
        })
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        self.write({'state': 'draft', 'created_count': 0,
                    'skipped_count': 0, 'calendar_count': 0})
        return self._reopen()
