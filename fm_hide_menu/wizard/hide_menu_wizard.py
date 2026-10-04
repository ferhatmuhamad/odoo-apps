# -*- coding: utf-8 -*-
"""Doing the same thing to twenty people at once.

Hiding one app for one person is a two-second job on their user form. The
reason this wizard exists is the other case: a new branch starts on
Monday, fifteen accounts, and none of them should see Purchase.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HideMenuWizard(models.TransientModel):
    _name = 'fm.hide.menu.wizard'
    _description = "Hide Menus for Several Users"

    mode = fields.Selection([
        ('add', "Hide these"),
        ('remove', "Show these again"),
        ('replace', "Make this the whole list"),
    ], default='add', required=True,
        help="Add leaves whatever is already hidden alone. Replace sets each selected user's "
             "hidden list to exactly what is picked here.")
    user_ids = fields.Many2many('res.users', string="Users", required=True,
                                domain=[('share', '=', False)])
    group_id = fields.Many2one(
        'res.groups', string="…or everyone in this group",
        help="Picking a group fills the list of users with its members.")
    app_ids = fields.Many2many(
        'ir.ui.menu', 'fm_hide_wizard_app_rel', 'wizard_id', 'menu_id',
        string="Apps", domain=[('parent_id', '=', False)])
    menu_ids = fields.Many2many(
        'ir.ui.menu', 'fm_hide_wizard_menu_rel', 'wizard_id', 'menu_id',
        string="Menus", domain=[('parent_id', '!=', False)])

    @api.onchange('group_id')
    def _onchange_group_id(self):
        if self.group_id:
            members = self.group_id.sudo().users if 'users' in self.group_id._fields \
                else self.group_id.sudo().user_ids
            self.user_ids = members.filtered(lambda user: not user.share)

    def action_apply(self):
        self.ensure_one()
        if not self.app_ids and not self.menu_ids and self.mode != 'replace':
            raise UserError(_("Pick at least one app or menu."))
        for user in self.user_ids:
            if self.mode == 'add':
                values = {'fm_hidden_app_ids': [(4, menu.id) for menu in self.app_ids],
                          'fm_hidden_menu_ids': [(4, menu.id) for menu in self.menu_ids]}
            elif self.mode == 'remove':
                values = {'fm_hidden_app_ids': [(3, menu.id) for menu in self.app_ids],
                          'fm_hidden_menu_ids': [(3, menu.id) for menu in self.menu_ids]}
            else:
                values = {'fm_hidden_app_ids': [(6, 0, self.app_ids.ids)],
                          'fm_hidden_menu_ids': [(6, 0, self.menu_ids.ids)]}
            user.sudo().write(values)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("%(count)s user(s) updated. They see the change on their next page load.",
                             count=len(self.user_ids)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
