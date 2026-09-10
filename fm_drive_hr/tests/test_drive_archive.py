# -*- coding: utf-8 -*-
"""Uji arsip karyawan, riwayat versi, dan masa berlaku dokumen (Tahap 3).

Janji yang dijaga di sini: arsip kepegawaian tidak boleh terbaca orang yang
tidak berhak (termasuk atasan langsung), versi lama tidak boleh hilang saat
berkas diunggah ulang, dan kuota harus ikut menghitung versi lama - kalau
tidak, satu orang bisa melewati jatahnya cukup dengan mengunggah berkas yang
sama berulang kali.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDriveArchive(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.Folder = cls.env['fm.drive.folder']
        cls.File = cls.env['fm.drive.file']
        cls.Employee = cls.env['hr.employee']

        # PENTING: grup ditulis eksplisit. Template pengguna bawaan
        # (`base.default_user`) di basis data ini memberi Manajer HR dan
        # beberapa grup administrator ke setiap akun baru, sehingga akun uji
        # yang dibuat tanpa `group_ids` akan LOLOS semua pemeriksaan hak dan
        # membuat uji ini kehilangan artinya.
        cls.plain_groups = [(6, 0, [cls.env.ref('base.group_user').id])]
        cls.staff_user = Users.create({
            'name': 'Karyawan Arsip', 'login': 'arc_staff',
            'group_ids': cls.plain_groups})
        cls.boss_user = Users.create({
            'name': 'Atasan', 'login': 'arc_boss', 'group_ids': cls.plain_groups})
        cls.hr_user = Users.create({
            'name': 'Staf HR', 'login': 'arc_hr',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('hr.group_hr_user').id])]})
        cls.hr_manager = Users.create({
            'name': 'Manajer HR', 'login': 'arc_hr_manager',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('hr.group_hr_manager').id])]})

        cls.boss = cls.Employee.create({'name': 'Atasan', 'user_id': cls.boss_user.id})
        cls.staff = cls.Employee.create({
            'name': 'Karyawan Arsip', 'user_id': cls.staff_user.id,
            'parent_id': cls.boss.id})

    def _archive_file(self, name='kontrak.pdf', folder=None):
        folder = folder or self.staff.drive_folder_id
        attachment = self.env['ir.attachment'].sudo().create({
            'name': name, 'raw': b'%PDF-1.4 ' + name.encode(),
            'res_model': 'fm.drive.file', 'res_id': 0})
        return self.File.sudo().create({
            'name': name, 'folder_id': folder.id, 'attachment_id': attachment.id,
            'owner_id': self.hr_manager.id, 'company_id': folder.company_id.id,
            'file_size': attachment.file_size, 'mimetype': 'application/pdf',
            'extension': 'pdf', 'checksum': attachment.checksum,
        })

    # ------------------------------------------------------------------
    # Pembentukan arsip
    # ------------------------------------------------------------------
    def test_new_employee_gets_an_archive(self):
        """Karyawan baru langsung punya folder arsip beserta sub foldernya."""
        self.assertTrue(self.staff.drive_folder_id,
                        "Karyawan baru tidak mendapat folder arsip")
        folder = self.staff.drive_folder_id
        self.assertEqual(folder.folder_type, 'employee')
        self.assertEqual(folder.employee_id, self.staff)

        names = {child.name for child in folder.child_ids}
        for expected in ('Contracts', 'Diplomas', 'Certificates', 'Insurance'):
            self.assertIn(expected, names,
                          "Sub folder %s tidak dibuat dari template" % expected)

    def test_archive_creation_is_idempotent(self):
        """Menjalankan pembentukan arsip berkali-kali tidak menggandakan folder."""
        before = len(self.staff.drive_folder_id.child_ids)
        self.staff._ensure_drive_folder()
        self.staff._ensure_drive_folder()
        self.assertEqual(len(self.staff.drive_folder_id.child_ids), before,
                         "Folder template tergandakan saat dijalankan ulang")

    def test_renaming_employee_renames_the_archive(self):
        self.staff.write({'name': 'Karyawan Arsip Baru'})
        self.assertEqual(self.staff.drive_folder_id.name, 'Karyawan Arsip Baru')

    def test_new_template_can_be_backfilled(self):
        Template = self.env['fm.drive.folder.template']
        Template.create({'name': 'Uji Susulan', 'sequence': 99})
        self.staff._sync_drive_template_folders()
        names = {child.name for child in self.staff.drive_folder_id.child_ids}
        self.assertIn('Uji Susulan', names,
                      "Template baru tidak tersusulkan ke arsip yang sudah ada")

    # ------------------------------------------------------------------
    # Hak akses arsip - bagian paling sensitif
    # ------------------------------------------------------------------
    def test_employee_sees_only_their_own_archive(self):
        doc = self._archive_file()
        as_staff = self.File.with_user(self.staff_user)
        self.assertTrue(as_staff.search([('id', '=', doc.id)]),
                        "Karyawan tidak bisa melihat dokumennya sendiri")

        other_user = self.env['res.users'].create({
            'name': 'Karyawan Lain', 'login': 'arc_other',
            'group_ids': self.plain_groups})
        other = self.Employee.create({'name': 'Karyawan Lain', 'user_id': other_user.id})
        self.assertTrue(other.drive_folder_id)
        self.assertFalse(self.File.with_user(other_user).search([('id', '=', doc.id)]),
                         "Karyawan bisa melihat dokumen karyawan lain")

    def test_direct_manager_gets_nothing(self):
        """Atasan langsung TIDAK otomatis melihat arsip bawahannya."""
        doc = self._archive_file('surat-peringatan.pdf')
        self.assertFalse(self.File.with_user(self.boss_user).search([('id', '=', doc.id)]),
                         "Atasan langsung bisa membaca arsip bawahannya")
        self.assertFalse(
            self.Folder.with_user(self.boss_user).search(
                [('id', '=', self.staff.drive_folder_id.id)]),
            "Atasan langsung bisa membuka folder arsip bawahannya")

    def test_hr_can_read_and_manager_can_write(self):
        doc = self._archive_file()
        as_hr = self.File.with_user(self.hr_user).browse(doc.id)
        self.assertTrue(as_hr._can_read(), "Staf HR tidak bisa membaca arsip")
        self.assertFalse(as_hr._can_write(),
                         "Staf HR biasa seharusnya tidak bisa mengubah arsip")

        as_manager = self.File.with_user(self.hr_manager).browse(doc.id)
        self.assertTrue(as_manager._can_write(), "Manajer HR tidak bisa mengelola arsip")

    def test_archive_root_hides_the_employee_list(self):
        """Akar "Arsip Karyawan" tidak boleh terbaca karyawan biasa.

        Di sana terlihat daftar nama semua orang yang punya arsip.
        """
        root = self.staff.drive_folder_id.parent_id
        self.assertTrue(root)
        self.assertFalse(
            self.Folder.with_user(self.staff_user).search([('id', '=', root.id)]),
            "Karyawan biasa bisa melihat daftar seluruh arsip karyawan")
        self.assertTrue(
            self.Folder.with_user(self.hr_user).search([('id', '=', root.id)]))

    def test_sidebar_gives_employee_a_shortcut(self):
        data = self.Folder.with_user(self.staff_user).get_browse_data(view='my')
        self.assertEqual(data['sidebar']['own_archive_id'],
                         self.staff.drive_folder_id.id,
                         "Jalan pintas ke arsip sendiri tidak dikirim ke antarmuka")
        self.assertFalse(data['sidebar']['archive_roots'],
                         "Karyawan biasa menerima daftar akar arsip")

    # ------------------------------------------------------------------
    # Riwayat versi
    # ------------------------------------------------------------------
    def _attachment(self, body, name='kontrak.pdf'):
        return self.env['ir.attachment'].sudo().create({
            'name': name, 'raw': body, 'res_model': 'fm.drive.file', 'res_id': 0})

    def test_new_version_keeps_the_old_content(self):
        doc = self._archive_file()
        original = doc.attachment_id
        doc.add_version(self._attachment(b'%PDF-1.4 revisi pertama'))

        self.assertEqual(doc.version_count, 1)
        version = doc.version_ids[0]
        self.assertEqual(version.attachment_id, original,
                         "Isi lama tidak tersimpan di riwayat")
        self.assertEqual(doc.attachment_id.raw, b'%PDF-1.4 revisi pertama')

    def test_restoring_a_version_is_itself_reversible(self):
        doc = self._archive_file()
        first_body = doc.attachment_id.raw
        doc.add_version(self._attachment(b'%PDF-1.4 revisi'))
        version = doc.version_ids[0]

        self.File.with_user(self.hr_manager).browse(doc.id).action_restore_version(version.id)
        self.assertEqual(doc.attachment_id.raw, first_body,
                         "Pemulihan versi tidak mengembalikan isi yang benar")
        self.assertEqual(doc.version_count, 1,
                         "Versi yang tergantikan tidak ikut masuk riwayat")
        self.assertIn('revisi', doc.version_ids[0].attachment_id.raw.decode())

    def test_versions_count_against_quota(self):
        """Versi lama adalah salinan penuh - harus ikut dihitung kuota."""
        Quota = self.env['fm.drive.quota']
        doc = self._archive_file()
        before = Quota._get_user_used_bytes(self.hr_manager)
        doc.add_version(self._attachment(b'x' * 5000))
        after = Quota._get_user_used_bytes(self.hr_manager)
        self.assertGreater(after, before,
                           "Versi lama tidak terhitung dalam pemakaian kuota")

    def test_version_history_needs_read_access(self):
        doc = self._archive_file()
        with self.assertRaises(UserError):
            self.File.with_user(self.boss_user).browse(doc.id).get_version_history()

    def test_restoring_a_foreign_version_is_rejected(self):
        doc_a = self._archive_file('a.pdf')
        doc_b = self._archive_file('b.pdf')
        doc_b.add_version(self._attachment(b'%PDF-1.4 b2'))
        foreign = doc_b.version_ids[0]
        with self.assertRaises(UserError):
            self.File.with_user(self.hr_manager).browse(doc_a.id).action_restore_version(
                foreign.id)

    # ------------------------------------------------------------------
    # Masa berlaku dokumen
    # ------------------------------------------------------------------
    def test_expiry_states(self):
        doc = self._archive_file()
        today = fields.Date.context_today(doc)

        doc.action_set_expiry(today + timedelta(days=200), 30)
        self.assertEqual(doc.expiry_state, 'ok')

        doc.action_set_expiry(today + timedelta(days=10), 30)
        self.assertEqual(doc.expiry_state, 'soon')

        doc.action_set_expiry(today - timedelta(days=1), 30)
        self.assertEqual(doc.expiry_state, 'expired')

        doc.action_set_expiry(False, 30)
        self.assertEqual(doc.expiry_state, 'none')

    def test_expiry_search_matches_the_computed_state(self):
        doc = self._archive_file()
        today = fields.Date.context_today(doc)
        doc.action_set_expiry(today + timedelta(days=5), 30)
        self.assertIn(doc, self.File.sudo().search([('expiry_state', '=', 'soon')]))
        self.assertNotIn(doc, self.File.sudo().search([('expiry_state', '=', 'ok')]))

        doc.action_set_expiry(today - timedelta(days=3), 30)
        self.assertIn(doc, self.File.sudo().search([('expiry_state', '=', 'expired')]))

    def test_reminder_runs_once_a_day(self):
        doc = self._archive_file()
        doc.action_set_expiry(fields.Date.context_today(doc) + timedelta(days=7), 30)

        sent = self.File._cron_expiry_reminders()
        self.assertGreaterEqual(sent, 1, "Pengingat tidak terkirim")
        self.assertEqual(doc.expiry_notified_date, fields.Date.context_today(doc))

        # Jalankan lagi di hari yang sama: berkas ini tidak boleh ikut lagi.
        logs_before = self.env['fm.drive.log'].sudo().search_count(
            [('action', '=', 'expiry_remind'), ('file_id', '=', doc.id)])
        self.File._cron_expiry_reminders()
        logs_after = self.env['fm.drive.log'].sudo().search_count(
            [('action', '=', 'expiry_remind'), ('file_id', '=', doc.id)])
        self.assertEqual(logs_before, logs_after,
                         "Pengingat untuk berkas yang sama terkirim dua kali sehari")

    def test_changing_the_date_resets_the_reminder(self):
        doc = self._archive_file()
        doc.action_set_expiry(fields.Date.context_today(doc) + timedelta(days=7), 30)
        self.File._cron_expiry_reminders()
        self.assertTrue(doc.expiry_notified_date)

        doc.action_set_expiry(fields.Date.context_today(doc) + timedelta(days=3), 30)
        self.assertFalse(doc.expiry_notified_date,
                         "Mengubah tanggal tidak menyetel ulang pengingat")

    def test_expiry_recipients_include_employee_and_hr(self):
        doc = self._archive_file()
        recipients = doc._expiry_recipients()
        self.assertIn(self.staff_user, recipients,
                      "Karyawan pemilik arsip tidak ikut dikabari")
        self.assertIn(self.hr_manager, recipients, "Manajer HR tidak ikut dikabari")
        self.assertNotIn(self.boss_user, recipients,
                         "Atasan langsung ikut dikabari padahal tidak berhak")

    def test_template_default_expiry_is_applied(self):
        """Berkas di folder "Kontrak" otomatis dapat masa berlaku."""
        kontrak = self.staff.drive_folder_id.child_ids.filtered(
            lambda f: f.name == 'Contracts')
        self.assertTrue(kontrak)
        doc = self._archive_file('kontrak-2026.pdf', folder=kontrak)
        doc._apply_folder_default_expiry()
        self.assertTrue(doc.date_expiry,
                        "Masa berlaku bawaan dari template tidak diterapkan")

    # ------------------------------------------------------------------
    # Remah roti (breadcrumb)
    # ------------------------------------------------------------------
    def test_breadcrumb_does_not_repeat_the_current_folder(self):
        """`parent_path` Odoo memuat record itu sendiri - jangan ikut digambar.

        Gejalanya dulu: "Employee Archive > Administrator > Diplomas > Diplomas".
        """
        kontrak = self.staff.drive_folder_id.child_ids.filtered(
            lambda f: f.name == 'Contracts')
        self.assertTrue(kontrak)

        data = self.Folder.with_user(self.hr_manager).get_browse_data(
            view='my', folder_id=kontrak.id)
        names = [c['name'] for c in data['breadcrumb']]

        self.assertNotIn('Contracts', names,
                         "Folder yang sedang dibuka ikut muncul di remah roti")
        self.assertEqual(names, ['Employee Archive', self.staff.name],
                         "Urutan leluhur salah: %s" % names)
        self.assertEqual(data['folder']['name'], 'Contracts')

    def test_root_folder_has_empty_breadcrumb(self):
        root = self.Folder.with_user(self.hr_manager).search([
            ('folder_type', '=', 'employee'), ('parent_id', '=', False)], limit=1)
        data = self.Folder.with_user(self.hr_manager).get_browse_data(
            view='my', folder_id=root.id)
        self.assertEqual(data['breadcrumb'], [],
                         "Folder akar seharusnya tanpa remah roti")

    def test_breadcrumb_hides_ancestors_the_user_cannot_read(self):
        """Karyawan membuka arsipnya sendiri tanpa galat hak akses.

        Akar "Arsip Karyawan" tidak boleh dibaca karyawan biasa. Sebelum
        diperbaiki, membaca nama leluhur itu melempar AccessError dan
        seluruh halaman gagal dimuat.
        """
        own = self.staff.drive_folder_id
        data = self.Folder.with_user(self.staff_user).get_browse_data(
            view='my', folder_id=own.id)
        self.assertEqual(data['folder']['name'], self.staff.name)
        self.assertEqual(data['breadcrumb'], [],
                         "Akar Arsip Karyawan bocor ke remah roti karyawan biasa")

        # Satu tingkat lebih dalam: leluhur yang BOLEH dibaca tetap tampil.
        kontrak = own.child_ids.filtered(lambda f: f.name == 'Contracts')
        data = self.Folder.with_user(self.staff_user).get_browse_data(
            view='my', folder_id=kontrak.id)
        self.assertEqual([c['name'] for c in data['breadcrumb']], [self.staff.name],
                         "Remah roti karyawan seharusnya berhenti di folder namanya")
