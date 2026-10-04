# -*- coding: utf-8 -*-
"""Where the hiding actually happens.

Odoo builds the menu twice: the row of apps (``get_user_roots``) and
everything underneath (``load_menus``, which asks ``_load_menus_blacklist``
what to leave out). Both are cached per user, so both are safe places to
take entries away for one person without touching anybody else's menu.
"""

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _fm_hidden_for_user(self):
        user = self.env.user
        if not user or self.env.su and self.env.uid == 1:
            # OdooBot builds menus for nobody; and the superuser must always
            # keep a complete menu, or a mistake could not be undone.
            return []
        if 'fm_hidden_app_ids' not in user._fields:
            return []
        return user._fm_hidden_menu_ids()

    def _load_menus_blacklist(self):
        return super()._load_menus_blacklist() + self._fm_hidden_for_user()

    # No @api.returns here: 19.0 dropped it, and an override inherits the
    # decorator from the method it overrides anyway.
    @api.model
    def get_user_roots(self):
        """17.0 and 18.0 build the app row without consulting the blacklist,
        so the apps have to be removed here as well."""
        roots = super().get_user_roots()
        hidden = self._fm_hidden_for_user()
        return roots.filtered(lambda menu: menu.id not in hidden) if hidden else roots
