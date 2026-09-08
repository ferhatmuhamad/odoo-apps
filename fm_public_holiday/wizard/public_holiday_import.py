from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PublicHolidayImport(models.TransientModel):
    _name = 'fm.public.holiday.import'
    _description = 'Import Public Holidays'

    country_ids = fields.Many2many(
        'res.country',
        string='Countries',
        help="Countries whose public holidays you want to add to your working "
             "schedules. Pick as many as you need.",
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
    apply_mode = fields.Selection(
        [('global', 'All working schedules (one entry per holiday)'),
         ('schedules', 'Specific working schedules')],
        string='Apply to',
        default='global',
        required=True,
        help="All working schedules: creates a single company-wide entry per "
             "holiday, and any schedule created later is covered automatically.\n"
             "Specific working schedules: creates one entry per schedule, so "
             "different offices can observe different holidays.",
    )
    calendar_ids = fields.Many2many(
        'resource.calendar',
        string='Working Schedules',
        help="Schedules that will receive the holidays. Leave empty to apply to every "
             "working schedule of the current company.",
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('select', 'Select'), ('done', 'Done')],
        default='draft',
        readonly=True,
    )
    holiday_ids = fields.Many2many(
        'fm.public.holiday',
        string='Holidays to Import',
        help="Uncheck any holiday you do not want to add to your schedules by "
             "removing its line.",
    )
    selected_count = fields.Integer(
        string='Selected', compute='_compute_selected', readonly=True)

    available_count = fields.Integer(
        string='Holidays Found', compute='_compute_available', readonly=True)
    country_count = fields.Integer(
        string='Countries Selected', compute='_compute_available', readonly=True)
    preview = fields.Text(string='Preview', compute='_compute_available', readonly=True)
    missing_country_ids = fields.Many2many(
        'res.country', 'fm_holiday_import_missing_rel', 'wizard_id', 'country_id',
        string='Countries Without Data', compute='_compute_available', readonly=True)
    missing_names = fields.Char(compute='_compute_available', readonly=True)
    library_available = fields.Boolean(
        string='Library Installed', compute='_compute_library', readonly=True)

    created_count = fields.Integer(string='Created', readonly=True)
    skipped_count = fields.Integer(string='Already Present', readonly=True)
    calendar_count = fields.Integer(string='Schedules Updated', readonly=True)

    @api.depends('holiday_ids')
    def _compute_selected(self):
        for wizard in self:
            wizard.selected_count = len(wizard.holiday_ids)

    @api.depends_context('uid')
    def _compute_library(self):
        available = self.env['fm.public.holiday']._library_available()
        for wizard in self:
            wizard.library_available = available

    @api.depends('country_ids', 'year_from', 'year_to')
    def _compute_available(self):
        Holiday = self.env['fm.public.holiday']
        for wizard in self:
            wizard.country_count = len(wizard.country_ids)
            if not wizard.country_ids or not wizard.year_from or not wizard.year_to:
                wizard.available_count = 0
                wizard.preview = False
                wizard.missing_country_ids = [(5, 0, 0)]
                wizard.missing_names = False
                continue

            # `_origin` resolves NewId records (an unsaved wizard in the form
            # view) back to their real database ids. Without it the dictionary
            # lookup below never matches and every country looks empty.
            countries = wizard.country_ids._origin
            groups = Holiday._read_group(
                [('country_id', 'in', countries.ids),
                 ('year', '>=', wizard.year_from),
                 ('year', '<=', wizard.year_to)],
                groupby=['country_id'],
                aggregates=['__count'],
            )
            counts = {country.id: count for country, count in groups}

            lines, total, missing_ids, missing_names = [], 0, [], []
            for country in countries.sorted('name'):
                found = counts.get(country.id, 0)
                total += found
                if found:
                    lines.append(_("%(country)s — %(count)s dates",
                                   country=country.name, count=found))
                else:
                    missing_ids.append(country.id)
                    missing_names.append(country.name)

            wizard.available_count = total
            wizard.preview = "\n".join(lines) or False
            wizard.missing_country_ids = [(6, 0, missing_ids)]
            wizard.missing_names = ", ".join(missing_names) or False

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------
    def action_select_all(self):
        """Select every country that already has data in the reference list."""
        self.ensure_one()
        groups = self.env['fm.public.holiday']._read_group([], groupby=['country_id'])
        country_ids = [country.id for (country,) in groups]
        self.country_ids = [(6, 0, country_ids)]
        return self._reopen()

    def action_clear_countries(self):
        self.ensure_one()
        self.country_ids = [(5, 0, 0)]
        return self._reopen()

    def action_load_holidays(self):
        """Move to the selection step with every matching holiday pre-checked."""
        self.ensure_one()
        self._check_input()
        holidays = self._find_holidays()
        if not holidays:
            raise UserError(_(
                "No holiday found for the selected countries between %(y1)s and "
                "%(y2)s.\n\nUse “Fetch from library” first if these countries are "
                "not part of the bundled data.",
                y1=self.year_from, y2=self.year_to,
            ))
        self.write({'state': 'select', 'holiday_ids': [(6, 0, holidays.ids)]})
        return self._reopen()

    def action_check_all_holidays(self):
        self.ensure_one()
        self.holiday_ids = [(6, 0, self._find_holidays().ids)]
        return self._reopen()

    def action_uncheck_all_holidays(self):
        self.ensure_one()
        self.holiday_ids = [(5, 0, 0)]
        return self._reopen()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _find_holidays(self):
        self.ensure_one()
        if not self.country_ids or not self.year_from or not self.year_to:
            return self.env['fm.public.holiday']
        return self.env['fm.public.holiday'].search([
            ('country_id', 'in', self.country_ids.ids),
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

    def _global_tz(self):
        """Timezone used for company-wide entries.

        A global entry has no working schedule, so `hr_holidays` performs no
        timezone conversion on it. We therefore resolve the timezone ourselves,
        preferring the company's default working schedule.
        """
        self.ensure_one()
        return (self.env.company.resource_calendar_id.tz
                or self.env.user.tz
                or 'UTC')

    @staticmethod
    def _bounds_in_tz(day, tz_name):
        tz = pytz.timezone(tz_name or 'UTC')
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC)
        end = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.UTC)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    def _day_bounds_utc(self, day):
        """Return the UTC datetimes covering a full day, expressed in the
        current user's timezone.

        `hr_holidays` re-bases public holidays from the user's timezone into the
        working schedule's timezone when the record is created
        (`_prepare_public_holidays_values`). Converting with the calendar
        timezone here would apply that shift twice, so we deliberately use the
        user timezone and let Odoo do the rest.
        """
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC)
        end = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.UTC)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    def _check_input(self):
        self.ensure_one()
        if not self.country_ids:
            raise UserError(_("Select at least one country."))
        if self.year_to < self.year_from:
            raise UserError(_("The last year cannot be earlier than the first year."))
        if self.year_to - self.year_from > 20:
            raise UserError(_("Please import at most 21 years at a time."))

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_fetch_from_library(self):
        """Pull holidays from the optional `holidays` package.

        Only the selected countries that have no data yet are fetched.
        """
        self.ensure_one()
        self._check_input()
        targets = (self.missing_country_ids or self.country_ids)._origin
        Holiday = self.env['fm.public.holiday']
        created = 0
        for country in targets:
            if not country.code:
                continue
            created += Holiday._fetch_from_library(
                country.code, self.year_from, self.year_to)
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

    def action_import(self):
        """Copy the selected holidays into the working schedules."""
        self.ensure_one()
        self._check_input()

        holidays = self.holiday_ids.sorted('date')
        if not holidays:
            raise UserError(_(
                "Every holiday has been unchecked, so there is nothing to import."
            ))

        if self.apply_mode == 'global':
            created, skipped, touched = self._import_global(holidays)
        else:
            created, skipped, touched = self._import_per_schedule(holidays)

        self.write({
            'state': 'done',
            'created_count': created,
            'skipped_count': skipped,
            'calendar_count': touched,
        })
        return self._reopen()

    def _import_global(self, holidays):
        """Create one company-wide entry per holiday (no working schedule).

        Odoo treats a leave without `calendar_id` as applying to every schedule
        (`resource.calendar._leave_intervals_batch`), so one record is enough
        and schedules created later are covered too.
        """
        self.ensure_one()
        Leave = self.env['resource.calendar.leaves']
        tz_name = self._global_tz()
        tz = pytz.timezone(tz_name)

        # Odoo refuses two overlapping public holidays in the same company,
        # and a global entry is checked against every schedule. So any date that
        # already carries a public holiday - global or per schedule - is skipped.
        taken = {
            pytz.UTC.localize(leave.date_from).astimezone(tz).date()
            for leave in Leave.search([
                ('resource_id', '=', False),
                ('company_id', 'in', [False, self.env.company.id]),
            ])
            if leave.date_from
        }

        vals_list, created, skipped = [], 0, 0
        for holiday in holidays:
            if holiday.date in taken:
                skipped += 1
                continue
            taken.add(holiday.date)
            date_from, date_to = self._bounds_in_tz(holiday.date, tz_name)
            vals_list.append({
                'name': holiday.name,
                'calendar_id': False,
                'company_id': self.env.company.id,
                'date_from': date_from,
                'date_to': date_to,
                'resource_id': False,
                'time_type': 'leave',
            })
        if vals_list:
            Leave.create(vals_list)
            created = len(vals_list)

        schedules = self.env['resource.calendar'].search_count([
            ('company_id', 'in', [False, self.env.company.id]),
        ])
        return created, skipped, schedules

    def _import_per_schedule(self, holidays):
        """Create one entry per working schedule."""
        self.ensure_one()
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
                existing.add(holiday.date)  # two countries may share a date
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
        return created, skipped, len(calendars)

    def action_back(self):
        """Return to the first step."""
        self.ensure_one()
        self.write({'state': 'draft', 'created_count': 0, 'skipped_count': 0,
                    'calendar_count': 0, 'holiday_ids': [(5, 0, 0)]})
        return self._reopen()
