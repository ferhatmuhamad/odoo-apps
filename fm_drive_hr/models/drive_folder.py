# -*- coding: utf-8 -*-
"""The per-employee archive folder kind.

``fm_drive`` knows two kinds of folder, personal and shared, and asks
``_custom_type_level`` about anything else. This module answers for a third:
``employee``, the archive HR keeps for each person.

WHO MAY LOOK
------------
HR reads everything, an employee sees their OWN archive, and a direct manager
is given nothing at all. That is deliberate: warning letters, contracts and
insurance papers are not a line manager's business. When there is a genuine
need, HR shares the document explicitly - and that sharing lands in the audit
log, which a silent blanket permission never would.
"""

from odoo import api, fields, models


class DriveFolder(models.Model):
    _inherit = 'fm.drive.folder'

    # 'set default' on purpose, NOT 'cascade': uninstalling this bridge must
    # never delete an employee's contracts. The folders fall back to the
    # ordinary personal kind and keep every file inside them.
    folder_type = fields.Selection(
        selection_add=[('employee', 'Employee Archive')],
        ondelete={'employee': 'set default'})

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', index=True, ondelete='cascade',
        help='Set on folders of the Employee Archive kind.')

    def _custom_type_level(self, user):
        if self.folder_type != 'employee':
            return super()._custom_type_level(user)
        if user.has_group('hr.group_hr_manager'):
            return 'write'
        if user.has_group('hr.group_hr_user'):
            return 'download'
        # The "Employee Archive" root belongs to no single person. Leaving it
        # readable would show everyone the LIST OF NAMES of everybody who has
        # an archive, which is itself information HR does not hand out.
        if self.employee_id and self.employee_id.sudo().user_id == user:
            return 'download'
        return None

    @api.model
    def _sidebar_extra(self, user):
        data = super()._sidebar_extra(user)
        is_hr = user.has_group('hr.group_hr_user')

        # An ordinary employee may not open the archive root, so they get a
        # shortcut straight to their own folder instead.
        own = self.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id), ('drive_folder_id', '!=', False)], limit=1)

        archive_roots = []
        if is_hr:
            archive_roots = [
                {'id': f.id, 'name': f.name}
                for f in self.search([('folder_type', '=', 'employee'),
                                      ('parent_id', '=', False),
                                      ('is_trashed', '=', False)])
            ]

        data.update({
            'is_hr': is_hr,
            'archive_roots': archive_roots,
            'own_archive_id': own.drive_folder_id.id if own else False,
            # Turns on the "Department" tab in the Share dialog. Without the
            # Employees app there are no departments to offer.
            'has_departments': True,
        })
        return data
