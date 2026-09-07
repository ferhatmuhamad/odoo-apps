from odoo import fields, models


class QuickNoteTag(models.Model):
    _name = 'fm.quick.note.tag'
    _description = 'Quick Note Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color')
    note_ids = fields.Many2many(
        'fm.quick.note',
        'fm_quick_note_tag_rel', 'tag_id', 'note_id',
        string='Notes',
    )
    note_count = fields.Integer(string='Number of Notes', compute='_compute_note_count')

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'A tag with this name already exists.',
    )

    def _compute_note_count(self):
        for tag in self:
            tag.note_count = len(tag.note_ids)
