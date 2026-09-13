# -*- coding: utf-8 -*-
"""A deadline that lives on a record rather than on an activity.

A task's deadline, a quotation's expiry date, an invoice's due date: each
is a date field on a model with a field that says whose it is. A source
names those two fields and, optionally, which records still count - a
task that is done has no deadline any more.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class DeadlineSource(models.Model):
    _name = 'fm.deadline.source'
    _description = 'Deadline Source'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True,
                       help='Shown as the badge on the alert, e.g. "Task deadline".')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade', string='Model')
    model_name = fields.Char(related='model_id.model', store=True)
    date_field_id = fields.Many2one(
        'ir.model.fields', required=True, ondelete='cascade', string='Deadline field',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime'))]")
    date_field_name = fields.Char(related='date_field_id.name', store=True)
    user_field_id = fields.Many2one(
        'ir.model.fields', required=True, ondelete='cascade', string='Assignee field',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('many2one', 'many2many')), ('relation', '=', 'res.users')]",
        help='The field that says whose record it is: a user, or several.')
    user_field_name = fields.Char(related='user_field_id.name', store=True)
    domain = fields.Char(
        string='Only records matching', default='[]',
        help='Records that still count. A done task, a paid invoice or a lost lead '
             'has no deadline any more; say so here.')
    icon = fields.Char(default='fa-calendar', help='A Font Awesome icon name, e.g. fa-tasks.')

    @api.constrains('domain')
    def _check_domain(self):
        for src in self:
            try:
                value = safe_eval(src.domain or '[]')
            except Exception:
                raise ValidationError(_('The domain of %s is not valid Python.', src.name))
            if not isinstance(value, list):
                raise ValidationError(_('The domain of %s must be a list.', src.name))

    def _domain(self):
        self.ensure_one()
        return safe_eval(self.domain or '[]')

    def _register_hook(self):
        # Runs once the whole registry is loaded - every model that exists
        # is known by now, whatever order the modules were installed in.
        super()._register_hook()
        from ..hooks import seed_sources
        try:
            seed_sources(self.env)
        except Exception:  # never let a seed keep the server from starting
            pass
