from odoo import api, fields, models


class QuickNote(models.Model):
    _name = 'fm.quick.note'
    _description = 'Quick Note'
    _order = 'is_pinned desc, priority desc, id desc'

    name = fields.Char(string='Title', required=True, index='trigram')
    content = fields.Text(string='Content')
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        required=True,
        index=True,
        ondelete='cascade',
        default=lambda self: self.env.user,
    )
    tag_ids = fields.Many2many(
        'fm.quick.note.tag',
        'fm_quick_note_tag_rel', 'note_id', 'tag_id',
        string='Tags',
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Important'),
            ('2', 'Urgent'),
        ],
        string='Priority',
        default='0',
        required=True,
    )
    is_pinned = fields.Boolean(string='Pinned')
    date_deadline = fields.Date(string='Deadline')
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        help='The deadline of this note is in the past.',
    )
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(string='Active', default=True)

    _title_not_empty = models.Constraint(
        "CHECK(length(trim(name)) > 0)",
        'The note title cannot be empty.',
    )

    @api.depends('date_deadline')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for note in self:
            note.is_overdue = bool(note.date_deadline and note.date_deadline < today)

    def action_toggle_pin(self):
        """Pin or unpin the selected notes."""
        for note in self:
            note.is_pinned = not note.is_pinned
        return True
