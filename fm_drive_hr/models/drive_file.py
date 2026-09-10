# -*- coding: utf-8 -*-
"""Document lifetimes inside an employee archive."""

from odoo import fields, models


class DriveFile(models.Model):
    _inherit = 'fm.drive.file'

    def _apply_folder_default_expiry(self):
        """Date a file from the lifetime carried by its archive folder.

        An archive folder such as "Contracts" or "Certificates" can be given a
        document lifetime on its template, so HR does not have to type a date
        for 260 employees one at a time - which in practice means the field is
        left empty and the reminder never fires.
        """
        super()._apply_folder_default_expiry()
        Template = self.env['fm.drive.folder.template'].sudo()
        for rec in self:
            folder = rec.folder_id.sudo()
            if folder.folder_type != 'employee' or rec.date_expiry:
                continue
            template = Template.search([
                ('name', '=ilike', folder.name),
                '|', ('company_id', '=', False),
                ('company_id', '=', folder.company_id.id),
            ], limit=1)
            if template and template.default_expiry_months > 0:
                rec.sudo().write({
                    'date_expiry': fields.Date.add(
                        fields.Date.context_today(rec),
                        months=template.default_expiry_months),
                })
        return True

    def _expiry_recipients(self):
        """Add the employee concerned and HR Management to the reminder.

        Those are the people who can actually renew an expiring contract or
        certificate; the owner of the file alone often cannot.
        """
        users = super()._expiry_recipients()
        self.ensure_one()
        folder = self.folder_id.sudo()
        if folder.folder_type == 'employee':
            if folder.employee_id.user_id:
                users |= folder.employee_id.user_id
            hr_group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
            if hr_group:
                users |= hr_group.users
        return users.filtered(lambda u: u.active and not u.drive_blocked)
