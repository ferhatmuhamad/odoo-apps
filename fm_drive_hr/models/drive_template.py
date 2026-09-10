# -*- coding: utf-8 -*-
"""Employee archive folder templates.

The list of sub folders created inside every employee's archive - Contracts,
Diplomas, Certificates, Warning Letters and so on. It is maintained from a
menu and NOT written into the code, so HR can add to or rearrange the archive
structure without a redeploy.

A template added later can be backfilled into archives that already exist,
through the "Apply to All Employees" button.
"""

from odoo import api, fields, models


class DriveFolderTemplate(models.Model):
    _name = 'fm.drive.folder.template'
    _description = 'Employee Archive Folder Template'
    _order = 'sequence, id'

    name = fields.Char(string='Folder Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Char(string='Description')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty when this folder is created for employees in every company.')
    default_expiry_months = fields.Integer(
        string='Document Lifetime (months)', default=0,
        help='When filled in, files uploaded into this folder automatically get an'
             ' expiry date that many months ahead. Handy for contracts and'
             ' certificates. Enter 0 when the documents never expire.')

    _name_not_empty = models.Constraint(
        "CHECK (name <> '')",
        'The folder name must not be empty.',
    )

    @api.model
    def _for_company(self, company):
        """The templates that apply to a given company."""
        return self.search([
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ])

    def action_apply_to_all_employees(self):
        """Backfill these template folders into archives that already exist.

        Safe to run repeatedly: a folder that is already there is skipped, not
        created a second time.
        """
        employees = self.env['hr.employee'].sudo().search(
            [('drive_folder_id', '!=', False)])
        created = 0
        for employee in employees:
            created += employee._sync_drive_template_folders()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Templates applied',
                'message': "%d new folders were created in the archives of %d employees."
                           % (created, len(employees)),
                'type': 'success',
                'sticky': False,
            },
        }
