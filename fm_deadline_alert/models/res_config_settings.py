# -*- coding: utf-8 -*-
from odoo import fields, models

PARAM = 'fm_deadline_alert.'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_da_window_hours = fields.Integer(
        string='Warn this many hours ahead', default=24, config_parameter=PARAM + 'window_hours',
        help='Deadlines within this many hours appear in the bell. Overdue ones always do.')
    fm_da_toast = fields.Boolean(
        string='Pop a notification when a new alert arrives', default=True,
        config_parameter=PARAM + 'toast')
    fm_da_count_planned = fields.Boolean(
        string="Count planned activities in Odoo's activity badge", default=True,
        config_parameter=PARAM + 'count_planned',
        help="Odoo's own activity badge counts only today's and overdue activities. "
             "With this on, planned ones count too.")
