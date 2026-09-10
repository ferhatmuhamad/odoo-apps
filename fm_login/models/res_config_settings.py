# -*- coding: utf-8 -*-
"""Which login screen to show, and what colour to paint it.

Both are stored as `ir.config_parameter`, not as user preferences. That is
forced by the subject: the login page renders before anyone has signed in,
so there is no user to read a preference from. The choice is therefore
database-wide, and an administrator makes it for everyone.
"""

import re

from odoo import api, fields, models

STYLES = ('odoo', 'split', 'card', 'open')
HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
DEFAULT_COLOR = '#1C1C22'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_login_style = fields.Selection(
        [
            ('odoo', 'Odoo default'),
            ('split', 'Split'),
            ('card', 'Card'),
            ('open', 'Open'),
        ],
        string='Login screen', default='odoo',
        config_parameter='fm_login.style',
        help='Applies to everyone who signs in to this database.')

    fm_login_color = fields.Char(
        string='Background colour', default=DEFAULT_COLOR,
        config_parameter='fm_login.color',
        help='Six-digit hex, for example #1C1C22. Used by the Open screen.')

    # Whether the ground is light enough that text on it must be dark. Worked
    # out here rather than in the stylesheet so a badly chosen colour cannot
    # produce an unreadable login page - the one page nobody can recover from
    # without a shell.
    fm_login_on_light = fields.Boolean(
        string='Light background', readonly=True,
        config_parameter='fm_login.on_light')

    @api.onchange('fm_login_color')
    def _onchange_fm_login_color(self):
        for rec in self:
            rec.fm_login_on_light = self._is_light(rec.fm_login_color)

    @staticmethod
    def _is_light(value):
        """Relative luminance, so text stays readable whatever colour is set."""
        if not value or not HEX.match(value or ''):
            return False
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))

        def channel(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        lum = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
        return lum > 0.42

    def set_values(self):
        # A colour that is not a plain hex is refused rather than stored: it
        # ends up inside a style attribute, and "red; background:url(...)"
        # is not a colour.
        for rec in self:
            if rec.fm_login_color and not HEX.match(rec.fm_login_color.strip()):
                rec.fm_login_color = DEFAULT_COLOR
            elif rec.fm_login_color:
                rec.fm_login_color = rec.fm_login_color.strip().upper()
            rec.fm_login_on_light = self._is_light(rec.fm_login_color)
        return super().set_values()
