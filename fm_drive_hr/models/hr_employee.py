# -*- coding: utf-8 -*-
"""The Drive archive of each employee.

The structure that gets built:

    Employee Archive          <- one root per company, HR only
    +- Anna Klein             <- one folder per employee
       +- Contracts
       +- Diplomas
       +- Certificates
       +- Warning Letters
       +- Insurance

The sub folders come from `fm.drive.folder.template` rather than from the
code, so HR can change the archive structure without a developer.

WHO MAY LOOK
------------
HR sees everything; an employee sees only their own folder; a **direct
manager is given nothing automatically**. That is deliberate: warning
letters, contracts and insurance papers are not a line manager's business.
When there is a real need HR shares them one by one - and that sharing is
recorded.

An employee folder is created WHEN IT IS NEEDED, not up front for everybody:
260 employees x 5 sub folders is 1,560 empty records that may never be used.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    drive_folder_id = fields.Many2one(
        'fm.drive.folder', string='Drive Archive Folder', copy=False,
        ondelete='set null', index=True)
    drive_file_count = fields.Integer(string='Document Count',
                                      compute='_compute_drive_file_count')

    def _compute_drive_file_count(self):
        counts = {}
        with_folder = self.filtered('drive_folder_id')
        if with_folder:
            Folder = self.env['fm.drive.folder'].sudo()
            for employee in with_folder:
                branch = Folder.search([('id', 'child_of', employee.drive_folder_id.id)])
                counts[employee.id] = self.env['fm.drive.file'].sudo().search_count([
                    ('folder_id', 'in', branch.ids), ('is_trashed', '=', False)])
        for employee in self:
            employee.drive_file_count = counts.get(employee.id, 0)

    # ------------------------------------------------------------------
    # Building the archive
    # ------------------------------------------------------------------
    @api.model
    def _get_employee_archive_root(self, company):
        """A company's "Employee Archive" root, created if it is missing."""
        Folder = self.env['fm.drive.folder'].sudo()
        root = Folder.search([
            ('folder_type', '=', 'employee'),
            ('parent_id', '=', False),
            ('company_id', '=', company.id),
        ], limit=1)
        if not root:
            admin = self.env.ref('base.user_admin', raise_if_not_found=False)
            root = Folder.create({
                'name': 'Employee Archive',
                'folder_type': 'employee',
                'company_id': company.id,
                'owner_id': (admin or self.env.user).id,
                'description': 'Personnel documents of %s' % company.name,
            })
        return root

    def _ensure_drive_folder(self):
        """Make sure the employee has an archive folder and its sub folders."""
        Folder = self.env['fm.drive.folder'].sudo()
        created_folders = 0
        for employee in self:
            company = employee.company_id or self.env.company
            if not employee.drive_folder_id:
                root = self._get_employee_archive_root(company)
                folder = Folder.create({
                    'name': employee.name,
                    'parent_id': root.id,
                    'folder_type': 'employee',
                    'company_id': company.id,
                    'owner_id': root.owner_id.id,
                    'employee_id': employee.id,
                })
                employee.sudo().write({'drive_folder_id': folder.id})
                created_folders += 1
            created_folders += employee._sync_drive_template_folders()
        return created_folders

    def _sync_drive_template_folders(self):
        """Create the template sub folders that are missing. Repeat-safe."""
        Folder = self.env['fm.drive.folder'].sudo()
        Template = self.env['fm.drive.folder.template']
        created = 0
        for employee in self:
            parent = employee.drive_folder_id
            if not parent or parent.is_trashed:
                continue
            existing = {child.name.lower() for child in parent.child_ids}
            for template in Template._for_company(employee.company_id or self.env.company):
                if template.name.lower() in existing:
                    continue
                Folder.create({
                    'name': template.name,
                    'parent_id': parent.id,
                    'folder_type': 'employee',
                    'company_id': parent.company_id.id,
                    'owner_id': parent.owner_id.id,
                    'employee_id': employee.id,
                    'description': template.description or False,
                })
                created += 1
        return created

    def action_open_drive_folder(self):
        """Button on the employee card: open their archive in the Drive app."""
        self.ensure_one()
        self._ensure_drive_folder()
        action = self.env['ir.actions.actions']._for_xml_id(
            'fm_drive.action_drive_app')
        action['context'] = {'drive_open_folder_id': self.drive_folder_id.id}
        return action

    # ------------------------------------------------------------------
    # ORM guards
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        # A new employee gets an archive straight away, so HR never has to
        # remember to create one by hand when somebody joins.
        try:
            employees._ensure_drive_folder()
        except Exception:  # noqa: BLE001
            # Building the archive must never fail the employee creation.
            _logger.warning("Team Drive: could not create the archive for a new employee",
                            exc_info=True)
        return employees

    def write(self, vals):
        res = super().write(vals)
        # The archive folder is renamed too, so the same person never ends up
        # under two different names.
        if 'name' in vals:
            for employee in self.filtered('drive_folder_id'):
                if employee.drive_folder_id.name != employee.name:
                    employee.drive_folder_id.sudo().write({'name': employee.name})
        return res

    # ------------------------------------------------------------------
    # Scheduler / bulk actions
    # ------------------------------------------------------------------
    @api.model
    def _cron_build_employee_archives(self):
        """Backfill archives for active employees that have none.

        Runs once a day as a safety net: employees created through a bulk
        import, or through any path that bypasses `create()`, still end up
        with an archive.
        """
        pending = self.sudo().search([
            ('active', '=', True), ('drive_folder_id', '=', False)], limit=200)
        if not pending:
            return 0
        created = pending._ensure_drive_folder()
        _logger.info("Team Drive: archives created for %d employees (%d folders)",
                     len(pending), created)
        return len(pending)
