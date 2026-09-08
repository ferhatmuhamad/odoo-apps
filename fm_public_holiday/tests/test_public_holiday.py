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
        # pinned so the timezone assertions below are deterministic
        cls.env.user.tz = 'Europe/Brussels'
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Test Schedule',
            'tz': 'Asia/Jakarta',
        })

    def _wizard(self, **kw):
        vals = {
            'country_id': self.indonesia.id,
            'year_from': 2026,
            'year_to': 2026,
            'calendar_ids': [(6, 0, self.calendar.ids)],
        }
        vals.update(kw)
        return self.Wizard.create(vals)

    def test_bundled_data_is_loaded(self):
        """The module ships holidays for the 16 bundled countries."""
        self.assertTrue(
            self.Holiday.search_count([('country_id', '=', self.indonesia.id)]) > 0,
            "Indonesian holidays should be part of the bundled data",
        )

    def test_year_is_computed_from_date(self):
        holiday = self.Holiday.search([('country_id', '=', self.indonesia.id)], limit=1)
        self.assertEqual(holiday.year, holiday.date.year)

    def test_preview_counts_available_holidays(self):
        wizard = self._wizard()
        expected = self.Holiday.search_count([
            ('country_id', '=', self.indonesia.id), ('year', '=', 2026)])
        self.assertEqual(wizard.available_count, expected)
        self.assertTrue(wizard.preview)

    def test_import_creates_calendar_leaves(self):
        wizard = self._wizard()
        expected = wizard.available_count
        self.assertTrue(expected, "there should be bundled data for 2026")
        wizard.action_import()
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.created_count, expected)
        self.assertEqual(
            self.Leave.search_count([('calendar_id', '=', self.calendar.id)]),
            expected,
        )

    def test_import_twice_skips_existing(self):
        """Running the import again must not duplicate anything."""
        first = self._wizard()
        first.action_import()
        created = first.created_count

        second = self._wizard()
        second.action_import()
        self.assertEqual(second.created_count, 0)
        self.assertEqual(second.skipped_count, created)
        self.assertEqual(
            self.Leave.search_count([('calendar_id', '=', self.calendar.id)]),
            created,
        )

    def test_leave_covers_the_whole_local_day(self):
        wizard = self._wizard()
        wizard.action_import()
        leave = self.Leave.search(
            [('calendar_id', '=', self.calendar.id)], order='date_from', limit=1)
        # Jakarta is UTC+7, so a local day starts at 17:00 UTC the day before
        self.assertEqual(leave.date_from.hour, 17)
        self.assertEqual((leave.date_to - leave.date_from).days, 0)
        self.assertGreater((leave.date_to - leave.date_from).seconds, 23 * 3600)

    def test_reversed_years_are_rejected(self):
        wizard = self._wizard(year_from=2027, year_to=2026)
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_country_without_data_raises(self):
        antarctica = self.env.ref('base.aq')
        wizard = self._wizard(country_id=antarctica.id)
        with self.assertRaises(UserError):
            wizard.action_import()
