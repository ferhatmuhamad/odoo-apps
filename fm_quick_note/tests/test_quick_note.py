from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools import mute_logger


class TestQuickNote(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Note = cls.env['fm.quick.note']
        cls.tag = cls.env['fm.quick.note.tag'].create({'name': 'Test Tag'})

    def test_default_owner_is_current_user(self):
        note = self.Note.create({'name': 'A note'})
        self.assertEqual(note.user_id, self.env.user)

    def test_overdue_is_computed_from_deadline(self):
        today = fields.Date.context_today(self.Note)
        past = self.Note.create({'name': 'Past', 'date_deadline': today - timedelta(days=1)})
        future = self.Note.create({'name': 'Future', 'date_deadline': today + timedelta(days=1)})
        no_deadline = self.Note.create({'name': 'None'})
        self.assertTrue(past.is_overdue)
        self.assertFalse(future.is_overdue)
        self.assertFalse(no_deadline.is_overdue)

    def test_toggle_pin_flips_the_flag(self):
        note = self.Note.create({'name': 'Pin me'})
        self.assertFalse(note.is_pinned)
        note.action_toggle_pin()
        self.assertTrue(note.is_pinned)
        note.action_toggle_pin()
        self.assertFalse(note.is_pinned)

    def test_tag_note_count(self):
        self.Note.create({'name': 'Tagged one', 'tag_ids': [(4, self.tag.id)]})
        self.Note.create({'name': 'Tagged two', 'tag_ids': [(4, self.tag.id)]})
        self.tag.invalidate_recordset(['note_ids', 'note_count'])
        self.assertEqual(self.tag.note_count, 2)

    def test_notes_are_ordered_pinned_first(self):
        low = self.Note.create({'name': 'Low', 'priority': '0'})
        pinned = self.Note.create({'name': 'Pinned', 'priority': '0', 'is_pinned': True})
        ordered = self.Note.search([('id', 'in', (low | pinned).ids)])
        self.assertEqual(ordered[0], pinned)

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_user_cannot_read_notes_of_others(self):
        other = new_test_user(
            self.env, login='qn_other', groups='fm_quick_note.group_quick_note_user',
        )
        mine = self.Note.create({'name': 'Mine only'})
        with self.assertRaises(AccessError):
            mine.with_user(other).read(['name'])
