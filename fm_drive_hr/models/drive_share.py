# -*- coding: utf-8 -*-
"""Sharing with a whole department.

``fm_drive`` shares with named people. This adds a second target kind: one
department, with its child departments inheriting the permission - sharing
with "Manufacturing" is naturally understood to reach the teams under it.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DriveShare(models.Model):
    _inherit = 'fm.drive.share'

    # 'cascade' is right here: without this module a department share
    # resolves to nobody, so leaving the row would be a permission that
    # silently grants nothing.
    target_type = fields.Selection(
        selection_add=[('department', 'One department')],
        ondelete={'department': 'cascade'})

    department_id = fields.Many2one('hr.department', string='Department',
                                    ondelete='cascade')

    # Odoo REPLACES the depends of an overridden compute rather than merging
    # them, so the inherited ones are repeated here on purpose.
    @api.depends('target_type', 'user_ids', 'department_id')
    def _compute_target_display(self):
        super()._compute_target_display()
        for share in self:
            if share.target_type == 'department':
                share.target_display = share.department_id.name or ''

    @api.constrains('target_type', 'department_id')
    def _check_department_filled(self):
        for share in self:
            if share.target_type == 'department' and not share.department_id:
                raise ValidationError("Choose a target department.")

    def _resolve_users(self):
        self.ensure_one()
        if self.target_type != 'department':
            return super()._resolve_users()
        departments = self.env['hr.department'].sudo().search(
            [('id', 'child_of', self.department_id.id)])
        employees = self.env['hr.employee'].sudo().search(
            [('department_id', 'in', departments.ids), ('user_id', '!=', False)])
        return employees.mapped('user_id')

    @api.model
    def _recipient_domain(self, user):
        return super()._recipient_domain(user) + [
            ('department_id', 'in', self._department_scope(user)),
        ]

    @api.model
    def _department_scope(self, user):
        """The user's departments and every parent above them.

        Used to match permissions shared with a PARENT department: a share on
        "Manufacturing" has to be readable by someone in a team below it.
        Deliberately goes through `hr.employee` with sudo rather than
        `user.employee_id`, because an employee can sit in a company that is
        not active for the user, and then `employee_id` is empty with no
        warning at all.
        """
        employees = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)])
        ids = set()
        for department in employees.mapped('department_id'):
            ids.add(department.id)
            ids.update(int(x) for x in (department.parent_path or '').split('/') if x)
        return list(ids)

    def _to_dict(self):
        data = super()._to_dict()
        data['department_id'] = self.department_id.id or False
        return data

    @api.model
    def _target_vals(self, target_type, values):
        vals = super()._target_vals(target_type, values)
        if target_type == 'department':
            vals['department_id'] = int(values.get('department_id') or 0) or False
        return vals
