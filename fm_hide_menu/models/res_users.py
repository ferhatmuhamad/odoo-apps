# -*- coding: utf-8 -*-
"""Which apps and menus a particular person should not be shown.

Two lists, because people think about them differently: whole apps
(Calendar, Discuss, Contacts) and single menu entries inside an app they
otherwise use.

This hides; it does not forbid. Somebody who knows the URL can still open
what is hidden, exactly as before. Taking access away is what access
rights are for - this is for tidying a screen that has grown too busy.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SETTINGS_MENU = 'base.menu_administration'


class ResUsers(models.Model):
    _inherit = 'res.users'

    fm_hidden_app_ids = fields.Many2many(
        'ir.ui.menu', 'fm_hide_menu_app_rel', 'user_id', 'menu_id',
        string="Hidden apps", domain=[('parent_id', '=', False)],
        help="Whole applications this person does not see in the menu. Everything inside them "
             "goes too.")
    fm_hidden_menu_ids = fields.Many2many(
        'ir.ui.menu', 'fm_hide_menu_menu_rel', 'user_id', 'menu_id',
        string="Hidden menus", domain=[('parent_id', '!=', False)],
        help="Single menu entries this person does not see. Anything underneath them goes too.")
    fm_hidden_count = fields.Integer(string="Hidden", compute='_compute_fm_hidden_count')

    @api.depends('fm_hidden_app_ids', 'fm_hidden_menu_ids')
    def _compute_fm_hidden_count(self):
        for user in self:
            user.fm_hidden_count = len(user.fm_hidden_app_ids) + len(user.fm_hidden_menu_ids)

    @api.constrains('fm_hidden_app_ids', 'fm_hidden_menu_ids')
    def _check_hidden_menus(self):
        for user in self:
            wrong = user.fm_hidden_app_ids.filtered('parent_id')
            if wrong:
                raise ValidationError(_("'Hidden apps' takes whole applications. %s is a menu "
                                        "inside one - put it in 'Hidden menus'.", wrong[0].name))

    # ── what the menu loader asks for ────────────────────────────────────
    def _fm_hidden_menu_ids(self):
        """Every menu id to keep from this user: what was picked, and
        everything underneath it."""
        self.ensure_one()
        picked = self.sudo().fm_hidden_app_ids | self.sudo().fm_hidden_menu_ids
        if not picked:
            return []
        hidden = self.env['ir.ui.menu'].sudo().search([('id', 'child_of', picked.ids)])
        # Never take away the way back: an administrator who hides Settings
        # would have nowhere left to undo it.
        if self.has_group('base.group_system'):
            settings = self.env.ref(SETTINGS_MENU, raise_if_not_found=False)
            if settings:
                hidden -= self.env['ir.ui.menu'].sudo().search([('id', 'child_of', settings.ids)])
        return hidden.ids

    # ── the menu is cached per user; a change has to reach it ────────────
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if any(self._fm_touches_menus(vals) for vals in vals_list):
            self.env.registry.clear_cache()
        return users

    def write(self, vals):
        result = super().write(vals)
        if self._fm_touches_menus(vals):
            self.env.registry.clear_cache()
        return result

    @staticmethod
    def _fm_touches_menus(vals):
        return bool({'fm_hidden_app_ids', 'fm_hidden_menu_ids'} & set(vals or {}))

    # ── buttons ──────────────────────────────────────────────────────────
    def action_fm_show_everything(self):
        """Give this person their whole menu back."""
        self.write({'fm_hidden_app_ids': [(5, 0, 0)], 'fm_hidden_menu_ids': [(5, 0, 0)]})
        return True
