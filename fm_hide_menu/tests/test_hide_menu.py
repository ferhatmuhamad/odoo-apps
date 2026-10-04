# -*- coding: utf-8 -*-
"""Hiding has to be exact: this person loses that entry, nobody else loses
anything, and the way back is never taken away."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHideMenu(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._user("Wira Worker", 'fmhm_wira')
        cls.other = cls._user("Other Person", 'fmhm_other')
        cls.Menu = cls.env['ir.ui.menu']
        # A real app with a real child, whatever is installed here.
        cls.app = cls.env.ref('base.menu_administration')
        cls.child = cls.Menu.search([('parent_id', 'child_of', cls.app.id)], limit=1) or \
            cls.Menu.search([('parent_id', '!=', False)], limit=1)
        cls.other_app = cls.Menu.search([('parent_id', '=', False), ('id', '!=', cls.app.id)], limit=1)

    @classmethod
    def _groups(cls, xmlids):
        key = 'group_ids' if 'group_ids' in cls.env['res.users']._fields else 'groups_id'
        return {key: [(6, 0, [cls.env.ref(x).id for x in xmlids])]}

    @classmethod
    def _user(cls, name, login, admin=False):
        groups = ['base.group_user'] + (['base.group_system'] if admin else [])
        return cls.env['res.users'].create({
            'name': name, 'login': login, 'email': '%s@example.com' % login,
            **cls._groups(groups)})

    def _roots(self, user):
        return self.Menu.with_user(user).get_user_roots()

    def _menus(self, user):
        return self.Menu.with_user(user).load_menus(False)

    # ── the two lists ────────────────────────────────────────────────────
    def test_an_app_is_gone_from_the_app_row(self):
        app = self.other_app
        self.assertIn(app, self._roots(self.user), "it is there to begin with")
        self.user.fm_hidden_app_ids = app
        self.assertNotIn(app, self._roots(self.user))

    def test_everything_inside_a_hidden_app_goes_too(self):
        app = self.other_app
        inside = self.Menu.search([('id', 'child_of', app.id), ('id', '!=', app.id)])
        self.user.fm_hidden_app_ids = app
        hidden = set(self.user._fm_hidden_menu_ids())
        self.assertTrue(set(inside.ids) <= hidden or not inside,
                        "the children of a hidden app are hidden as well")

    def test_a_single_menu_can_be_hidden_without_its_app(self):
        if not self.child:
            self.skipTest("no child menu in this database")
        app = self.child.sudo()._filter_visible_menus() and self.child
        self.user.fm_hidden_menu_ids = self.child
        hidden = self.user._fm_hidden_menu_ids()
        self.assertIn(self.child.id, hidden)
        self.assertNotIn(self.child.parent_id.id, hidden, "its app stays")

    def test_hiding_for_one_person_leaves_everybody_else_alone(self):
        app = self.other_app
        self.user.fm_hidden_app_ids = app
        self.assertNotIn(app, self._roots(self.user))
        self.assertIn(app, self._roots(self.other), "nobody else's menu changed")

    def test_an_app_cannot_be_put_in_the_menus_list_by_mistake(self):
        if not self.child:
            self.skipTest("no child menu in this database")
        with self.assertRaises(ValidationError):
            self.user.fm_hidden_app_ids = self.child

    def test_show_everything_again(self):
        self.user.fm_hidden_app_ids = self.other_app
        if self.child:
            self.user.fm_hidden_menu_ids = self.child
        self.assertTrue(self.user.fm_hidden_count)
        self.user.action_fm_show_everything()
        self.assertFalse(self.user.fm_hidden_count)
        self.assertIn(self.other_app, self._roots(self.user))

    # ── the way back ─────────────────────────────────────────────────────
    def test_an_administrator_always_keeps_settings(self):
        admin = self._user("Adi Admin", 'fmhm_adi', admin=True)
        admin.fm_hidden_app_ids = self.env.ref('base.menu_administration')
        self.assertNotIn(self.env.ref('base.menu_administration').id,
                         admin._fm_hidden_menu_ids(),
                         "hiding Settings from an admin would leave no way to undo it")

    def test_a_plain_user_may_lose_settings(self):
        # They never had it anyway; the rule is only about not stranding admins.
        self.user.fm_hidden_app_ids = self.env.ref('base.menu_administration')
        self.assertIn(self.env.ref('base.menu_administration').id, self.user._fm_hidden_menu_ids())

    def test_the_superuser_keeps_a_whole_menu(self):
        root = self.env.ref('base.user_root')
        root.sudo().fm_hidden_app_ids = self.other_app
        hidden = self.Menu.with_user(root).sudo()._fm_hidden_for_user()
        self.assertFalse(hidden, "the account that can repair everything is never trimmed")

    # ── the menu really is rebuilt ───────────────────────────────────────
    def test_the_loaded_menu_no_longer_lists_the_app(self):
        app = self.other_app
        before = self._menus(self.user)
        self.assertIn(app.id, before['root']['children'])
        self.user.fm_hidden_app_ids = app
        after = self._menus(self.user)
        self.assertNotIn(app.id, after['root']['children'],
                         "the cached menu was rebuilt after the change")

    def _a_child_this_user_sees(self, user):
        """A menu inside an app that this particular person actually has -
        the Settings children, for instance, are invisible to them anyway."""
        loaded = self._menus(user)
        for key, menu in loaded.items():
            if key != 'root' and menu.get('parent_id'):
                return self.Menu.browse(menu['id'])
        return self.Menu

    def test_a_hidden_entry_disappears_from_the_loaded_menu(self):
        child = self._a_child_this_user_sees(self.user)
        if not child:
            self.skipTest("this user has no menu entry inside an app")
        self.assertIn(child.id, self._menus(self.user), "it is there to begin with")
        self.user.fm_hidden_menu_ids = child
        self.assertNotIn(child.id, self._menus(self.user),
                         "a single entry really leaves the menu, not just the list")

    def test_a_hidden_entry_stays_for_everybody_else(self):
        child = self._a_child_this_user_sees(self.user)
        if not child:
            self.skipTest("this user has no menu entry inside an app")
        self.user.fm_hidden_menu_ids = child
        self.assertIn(child.id, self._menus(self.other))

    # ── the wizard ───────────────────────────────────────────────────────
    def _wizard(self, **values):
        return self.env['fm.hide.menu.wizard'].create(values)

    def test_the_wizard_hides_for_several_people_at_once(self):
        wizard = self._wizard(mode='add', user_ids=[(6, 0, (self.user | self.other).ids)],
                              app_ids=[(6, 0, self.other_app.ids)])
        wizard.action_apply()
        self.assertIn(self.other_app, self.user.fm_hidden_app_ids)
        self.assertIn(self.other_app, self.other.fm_hidden_app_ids)

    def test_the_wizard_can_give_menus_back(self):
        self.user.fm_hidden_app_ids = self.other_app
        self._wizard(mode='remove', user_ids=[(6, 0, self.user.ids)],
                     app_ids=[(6, 0, self.other_app.ids)]).action_apply()
        self.assertFalse(self.user.fm_hidden_app_ids)

    def test_replace_sets_the_whole_list(self):
        self.user.fm_hidden_app_ids = self.other_app
        other_root = self.Menu.search([('parent_id', '=', False),
                                       ('id', 'not in', (self.other_app | self.app).ids)], limit=1)
        if not other_root:
            self.skipTest("only two apps installed")
        self._wizard(mode='replace', user_ids=[(6, 0, self.user.ids)],
                     app_ids=[(6, 0, other_root.ids)]).action_apply()
        self.assertEqual(self.user.fm_hidden_app_ids, other_root)

    def test_the_wizard_fills_users_from_a_group(self):
        group = self.env.ref('base.group_user')
        wizard = self._wizard(mode='add', user_ids=[(6, 0, self.user.ids)],
                              app_ids=[(6, 0, self.other_app.ids)])
        wizard.group_id = group
        wizard._onchange_group_id()
        self.assertIn(self.user, wizard.user_ids)
        self.assertIn(self.other, wizard.user_ids)
