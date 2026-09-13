# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestDeadlineAlert(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.me = new_test_user(cls.env, login='da_me', groups='base.group_user')
        cls.other = new_test_user(cls.env, login='da_other', groups='base.group_user')
        cls.partner = cls.env['res.partner'].create({'name': 'Someone'})
        cls.todo = cls.env.ref('mail.mail_activity_data_todo')
        cls.today = fields.Date.context_today(cls.env['fm.deadline.alert'].with_user(cls.me))

    def _activity(self, user, days, summary='Call back', model='res.partner', res=None):
        res = res or self.partner
        return self.env['mail.activity'].create({
            'activity_type_id': self.todo.id, 'summary': summary,
            'res_model_id': self.env['ir.model']._get(model).id, 'res_id': res.id,
            'user_id': user.id, 'date_deadline': self.today + timedelta(days=days),
        })

    def _alerts(self, user=None):
        return self.env['fm.deadline.alert'].with_user(user or self.me).get_alerts()

    def _watch_bus(self):
        """bus.bus rows are written at commit, which a test never reaches:
        capture the calls instead."""
        calls = []
        Bus = type(self.env['bus.bus'])
        p = patch.object(Bus, '_sendone', autospec=True,
                         side_effect=lambda self_, target, ntype, message: calls.append((target, ntype)))
        p.start()
        self.addCleanup(p.stop)
        return calls

    # ── activities ───────────────────────────────────────────────────────

    def test_window_and_states(self):
        late = self._activity(self.me, -3, 'Late')
        today = self._activity(self.me, 0, 'Today')
        tomorrow = self._activity(self.me, 1, 'Tomorrow')
        self._activity(self.me, 2, 'Too far')
        self._activity(self.other, -1, 'Not mine')
        data = self._alerts()
        keys = [a['summary'] for a in data['alerts']]
        self.assertEqual(keys, ['Late', 'Today', 'Tomorrow'], 'overdue first, then by date; window is 24 h')
        by = {a['summary']: a for a in data['alerts']}
        self.assertEqual(by['Late']['state'], 'overdue')
        self.assertEqual(by['Late']['days'], -3)
        self.assertEqual(by['Today']['state'], 'today')
        self.assertEqual(by['Tomorrow']['state'], 'upcoming')
        self.assertEqual(by['Late']['title'], 'Someone', 'the record the activity is on')
        self.assertEqual(by['Late']['activity_id'], late.id)
        self.assertEqual(by['Late']['res_model'], 'res.partner')
        self.assertEqual(data['settings']['window_hours'], 24)

    def test_window_setting(self):
        self.env['ir.config_parameter'].sudo().set_param('fm_deadline_alert.window_hours', '72')
        self._activity(self.me, 3, 'Three days')
        self._activity(self.me, 4, 'Four days')
        self.assertEqual([a['summary'] for a in self._alerts()['alerts']], ['Three days'])

    def test_mark_done_only_own(self):
        mine = self._activity(self.me, 0)
        theirs = self._activity(self.other, 0)
        Alert = self.env['fm.deadline.alert'].with_user(self.me)
        Alert.mark_activity_done(mine.id)
        # 17.0/18.0 delete a done activity, 19.0 archives it
        self.assertFalse(mine.exists() and mine.active)
        Alert.mark_activity_done(theirs.id)
        self.assertTrue(theirs.exists() and theirs.active, "somebody else's activity is left alone")

    # ── record deadlines through a source ────────────────────────────────

    def _source(self, date_field, domain='[]', name='Deadline'):
        model = self.env['ir.model']._get('mail.activity')
        return self.env['fm.deadline.source'].create({
            'name': name, 'model_id': model.id,
            'date_field_id': self.env['ir.model.fields']._get('mail.activity', date_field).id,
            'user_field_id': self.env['ir.model.fields']._get('mail.activity', 'user_id').id,
            'domain': domain, 'icon': 'fa-flag',
        })

    def test_record_source_date_field(self):
        """mail.activity itself makes a fine guinea pig: a date field and a
        user field, no other app needed."""
        self._source('date_deadline', name='Activity deadline')
        self._activity(self.me, -1, 'Mine')
        self._activity(self.other, -1, 'Theirs')
        records = [a for a in self._alerts()['alerts'] if a['kind'] == 'record']
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['badge'], 'Activity deadline')
        self.assertEqual(records[0]['icon'], 'fa-flag')
        self.assertEqual(records[0]['state'], 'overdue')
        self.assertEqual(records[0]['res_model'], 'mail.activity')

    def test_record_source_datetime_field_and_domain(self):
        self._source('create_date', domain="[('summary', '=', 'Wanted')]", name='Created')
        self._activity(self.me, 5, 'Wanted')     # deadline out of window, but create_date is now
        self._activity(self.me, 5, 'Unwanted')
        records = [a for a in self._alerts()['alerts'] if a['kind'] == 'record']
        self.assertEqual([r['badge'] for r in records], ['Created'])
        self.assertEqual(records[0]['state'], 'overdue', 'a datetime a moment ago is overdue...')
        self.assertEqual(records[0]['days'], 0, '...by zero days: "earlier today"')

    def test_bad_domain_is_refused(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._source('date_deadline', domain='not a list')

    def test_seeded_sources_match_installed_apps(self):
        Source = self.env['fm.deadline.source'].sudo()
        for model, field in (('project.task', 'date_deadline'), ('crm.lead', 'date_deadline'),
                             ('sale.order', 'validity_date'), ('account.move', 'invoice_date_due')):
            seeded = bool(Source.search([('model_name', '=', model), ('date_field_name', '=', field)]))
            self.assertEqual(seeded, model in self.env, '%s: source iff the app is installed' % model)

    # ── the bus ──────────────────────────────────────────────────────────

    def test_bus_on_create_write_done_unlink(self):
        calls = self._watch_bus()
        mine = lambda: [c for c in calls if c[1] == 'fm_deadline_alert/refresh']
        act = self._activity(self.me, 0)
        self.assertEqual(len(mine()), 1, 'create tells the assignee')
        self.assertEqual(mine()[0][0], self.me.partner_id, 'on the partner channel')
        act.write({'user_id': self.other.id})
        self.assertEqual(len(mine()), 3, 'reassigning tells both')
        self.assertEqual({c[0] for c in mine()[1:]}, {self.me.partner_id, self.other.partner_id})
        act.write({'summary': 'x'})
        self.assertEqual(len(mine()), 4)
        act.write({'note': 'irrelevant'})
        self.assertEqual(len(mine()), 4, 'a note changes nothing on the bell')
        act.action_done()
        self.assertEqual(len(mine()), 5, 'done tells the assignee before the record goes')
        act2 = self._activity(self.me, 0)
        n = len(mine())
        act2.unlink()
        self.assertEqual(len(mine()), n + 1)
        if 'active' in act2._fields:  # 19.0: a done activity is archived, and can come back
            act3 = self._activity(self.me, 0)
            n = len(mine())
            act3.write({'active': False})
            self.assertEqual(len(mine()), n + 1, 'archiving tells the assignee')
            act3.write({'active': True})
            self.assertEqual(len(mine()), n + 2, 'so does bringing it back')

    # ── Odoo's own badge ─────────────────────────────────────────────────

    def test_planned_activities_count_in_badge(self):
        self._activity(self.me, 5, 'Planned')
        Users = self.env['res.users'].with_user(self.me)
        groups = Users.systray_get_activities() if self._has_17_api() else Users._get_activity_groups()
        group = next(g for g in groups if g['model'] == 'res.partner')
        self.assertEqual(group['total_count'], 1)
        self.env['ir.config_parameter'].sudo().set_param('fm_deadline_alert.count_planned', 'False')
        groups = Users.systray_get_activities() if self._has_17_api() else Users._get_activity_groups()
        group = next(g for g in groups if g['model'] == 'res.partner')
        self.assertEqual(group['total_count'], 0, "off: Odoo's own count, planned not included")

    def _has_17_api(self):
        import odoo
        return odoo.release.version_info[0] < 18
