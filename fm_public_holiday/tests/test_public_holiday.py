from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPublicHoliday(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Holiday = cls.env['fm.public.holiday']
        cls.Wizard = cls.env['fm.public.holiday.import']
        cls.Leave = cls.env['resource.calendar.leaves']
        cls.indonesia = cls.env.ref('base.id')
        cls.singapore = cls.env.ref('base.sg')
        # pinned so the timezone assertions below are deterministic
        cls.env.user.tz = 'Europe/Brussels'
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Test Schedule',
            'tz': 'Asia/Jakarta',
        })

    def _wizard(self, countries=None, **kw):
        vals = {
            'country_ids': [(6, 0, (countries or self.indonesia).ids)],
            'year_from': 2026,
            'year_to': 2026,
            'calendar_ids': [(6, 0, self.calendar.ids)],
        }
        vals.update(kw)
        return self.Wizard.create(vals)

    # ---------------- reference data ----------------

    def test_bundled_data_is_loaded(self):
        self.assertTrue(
            self.Holiday.search_count([('country_id', '=', self.indonesia.id)]) > 0,
            "Indonesian holidays should be part of the bundled data",
        )

    def test_year_is_computed_from_date(self):
        holiday = self.Holiday.search([('country_id', '=', self.indonesia.id)], limit=1)
        self.assertEqual(holiday.year, holiday.date.year)

    # ---------------- selection ----------------

    def test_preview_counts_per_country(self):
        wizard = self._wizard()
        expected = self.Holiday.search_count([
            ('country_id', '=', self.indonesia.id), ('year', '=', 2026)])
        self.assertEqual(wizard.available_count, expected)
        self.assertEqual(wizard.country_count, 1)
        self.assertIn(self.indonesia.name, wizard.preview)
        self.assertFalse(wizard.missing_names)

    def test_preview_works_on_an_unsaved_record(self):
        """The form view computes on a NewId record before it is saved.

        Regression test: `country.id` is a NewId there, so a plain dictionary
        lookup against real ids silently returned zero and every country was
        reported as having no data.
        """
        wizard = self.Wizard.new({
            'country_ids': [(6, 0, self.indonesia.ids)],
            'year_from': 2026,
            'year_to': 2026,
        })
        expected = self.Holiday.search_count([
            ('country_id', '=', self.indonesia.id), ('year', '=', 2026)])
        self.assertTrue(expected)
        self.assertEqual(wizard.available_count, expected)
        self.assertIn(self.indonesia.name, wizard.preview)
        self.assertFalse(
            wizard.missing_names,
            "Indonesia is bundled, it must not be reported as missing",
        )

    def test_multiple_countries_are_added_up(self):
        both = self.indonesia | self.singapore
        wizard = self._wizard(countries=both)
        expected = self.Holiday.search_count([
            ('country_id', 'in', both.ids), ('year', '=', 2026)])
        self.assertEqual(wizard.country_count, 2)
        self.assertEqual(wizard.available_count, expected)
        self.assertIn(self.singapore.name, wizard.preview)

    def test_select_all_picks_every_country_with_data(self):
        wizard = self._wizard()
        wizard.action_select_all()
        with_data = self.Holiday.search([]).mapped('country_id')
        self.assertEqual(set(wizard.country_ids.ids), set(with_data.ids))
        self.assertGreaterEqual(wizard.country_count, 16)

    def test_clear_empties_the_selection(self):
        wizard = self._wizard()
        wizard.action_clear_countries()
        self.assertFalse(wizard.country_ids)
        self.assertEqual(wizard.available_count, 0)

    def test_country_without_data_is_reported_as_missing(self):
        antarctica = self.env.ref('base.aq')
        wizard = self._wizard(countries=self.indonesia | antarctica)
        self.assertIn(antarctica, wizard.missing_country_ids)
        self.assertIn(antarctica.name, wizard.missing_names)

    # ---------------- import ----------------

    def test_import_creates_calendar_leaves(self):
        wizard = self._wizard()
        expected = wizard.available_count
        self.assertTrue(expected, "there should be bundled data for 2026")
        wizard.action_load_holidays()
        self.assertEqual(wizard.state, 'select')
        self.assertEqual(wizard.selected_count, expected)
        wizard.action_import()
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.created_count, expected)
        self.assertEqual(
            self.Leave.search_count([('calendar_id', '=', self.calendar.id)]),
            expected,
        )

    def test_import_twice_skips_existing(self):
        first = self._wizard()
        first.action_load_holidays()
        first.action_import()
        created = first.created_count

        second = self._wizard()
        second.action_load_holidays()
        second.action_import()
        self.assertEqual(second.created_count, 0)
        self.assertEqual(second.skipped_count, created)

    def test_shared_date_between_countries_is_created_once(self):
        """1 January exists in both countries but must not be created twice."""
        wizard = self._wizard(countries=self.indonesia | self.singapore)
        wizard.action_load_holidays()
        wizard.action_import()
        new_year = self.Leave.search_count([
            ('calendar_id', '=', self.calendar.id),
            ('date_from', '>=', '2025-12-31 00:00:00'),
            ('date_from', '<=', '2026-01-01 23:59:59'),
        ])
        self.assertEqual(new_year, 1)

    def test_leave_covers_the_whole_local_day(self):
        wizard = self._wizard()
        wizard.action_load_holidays()
        wizard.action_import()
        leave = self.Leave.search(
            [('calendar_id', '=', self.calendar.id)], order='date_from', limit=1)
        # Jakarta is UTC+7, so a local day starts at 17:00 UTC the day before
        self.assertEqual(leave.date_from.hour, 17)
        self.assertGreater((leave.date_to - leave.date_from).seconds, 23 * 3600)

    # ---------------- validation ----------------

    def test_no_country_selected_is_rejected(self):
        wizard = self._wizard()
        wizard.action_clear_countries()
        with self.assertRaises(UserError):
            wizard.action_load_holidays()

    def test_reversed_years_are_rejected(self):
        wizard = self._wizard(year_from=2027, year_to=2026)
        with self.assertRaises(UserError):
            wizard.action_load_holidays()

    def test_country_without_data_raises_on_load(self):
        antarctica = self.env.ref('base.aq')
        wizard = self._wizard(countries=antarctica)
        with self.assertRaises(UserError):
            wizard.action_load_holidays()

    # ---------------- picking individual holidays ----------------

    def test_unchecking_one_holiday_excludes_it(self):
        """Drop Christmas from the Indonesian list and it must not be imported."""
        wizard = self._wizard()
        wizard.action_load_holidays()
        total = wizard.selected_count

        christmas = wizard.holiday_ids.filtered(
            lambda h: h.date.month == 12 and h.date.day == 25)
        self.assertTrue(christmas, "Indonesia should have Christmas in 2026")

        wizard.holiday_ids = [(3, christmas.id)]
        self.assertEqual(wizard.selected_count, total - 1)

        wizard.action_import()
        self.assertEqual(wizard.created_count, total - 1)

        imported = self.Leave.search([('calendar_id', '=', self.calendar.id)])
        self.assertNotIn(christmas.name, imported.mapped('name'))

    def test_uncheck_all_then_import_is_rejected(self):
        wizard = self._wizard()
        wizard.action_load_holidays()
        wizard.action_uncheck_all_holidays()
        self.assertEqual(wizard.selected_count, 0)
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_check_all_restores_the_full_list(self):
        wizard = self._wizard()
        wizard.action_load_holidays()
        total = wizard.selected_count
        wizard.action_uncheck_all_holidays()
        wizard.action_check_all_holidays()
        self.assertEqual(wizard.selected_count, total)

    def test_back_resets_the_selection(self):
        wizard = self._wizard()
        wizard.action_load_holidays()
        wizard.action_back()
        self.assertEqual(wizard.state, 'draft')
        self.assertFalse(wizard.holiday_ids)
