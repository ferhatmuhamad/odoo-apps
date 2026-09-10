# -*- coding: utf-8 -*-
"""Sharing with a whole department.

The department target only exists while this bridge module is installed, so
these two tests live here rather than in fm_drive: a permission that reaches
the wrong people is the most expensive kind of bug this module can have.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDriveDepartmentShare(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.owner = Users.create({'name': 'Owner', 'login': 'dept_owner'})
        cls.mate = Users.create({'name': 'Colleague', 'login': 'dept_mate'})
        cls.outsider = Users.create({'name': 'Outsider', 'login': 'dept_outsider'})

        cls.Folder = cls.env['fm.drive.folder']
        cls.File = cls.env['fm.drive.file']
        cls.Share = cls.env['fm.drive.share']

        cls.root = cls.Folder.with_user(cls.owner)._get_personal_root(cls.owner)
        cls.sub = cls.Folder.with_user(cls.owner).browse(
            cls.Folder.with_user(cls.owner).create_folder('Project', cls.root.id)['id'])

    def _make_file(self, folder, name='document.pdf', user=None):
        user = user or self.owner
        attachment = self.env['ir.attachment'].sudo().create({
            'name': name, 'raw': b'x' * 64, 'mimetype': 'application/pdf',
        })
        return self.File.with_user(user).sudo().create({
            'name': name, 'folder_id': folder.id, 'owner_id': user.id,
            'attachment_id': attachment.id,
        })

    def test_department_share_includes_child_departments(self):
        """Sharing with a parent department reaches the teams below it."""
        Department = self.env['hr.department']
        parent = Department.create({'name': 'Test Manufacturing'})
        child = Department.create({'name': 'Test Team A', 'parent_id': parent.id})
        self.env['hr.employee'].create({
            'name': 'Team Member', 'user_id': self.mate.id, 'department_id': child.id})

        doc = self._make_file(self.sub)
        self.Share.with_user(self.owner).add_share(
            'fm.drive.file', doc.id,
            {'target_type': 'department', 'department_id': parent.id,
             'access_level': 'download'})

        self.assertTrue(self.File.with_user(self.mate).search([('id', '=', doc.id)]),
                        "A member of the child department did not receive the share")
        self.assertFalse(self.File.with_user(self.outsider).search([('id', '=', doc.id)]),
                         "The department share leaked outside the department")

    def test_bulk_share_to_department(self):
        Department = self.env['hr.department']
        dept = Department.create({'name': 'Test Bulk Dept'})
        self.env['hr.employee'].create({
            'name': 'Bulk Member', 'user_id': self.mate.id, 'department_id': dept.id})
        docs = [self._make_file(self.sub, 'dept-%d.pdf' % i) for i in range(2)]

        result = self.Share.with_user(self.owner).add_share_many(
            [['fm.drive.file', d.id] for d in docs],
            {'target_type': 'department', 'department_id': dept.id,
             'access_level': 'download'})

        self.assertEqual(result['done'], 2)
        for doc in docs:
            self.assertTrue(self.File.with_user(self.mate).search([('id', '=', doc.id)]))

