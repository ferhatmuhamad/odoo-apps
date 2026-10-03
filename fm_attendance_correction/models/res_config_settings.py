# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_ac_days_back = fields.Integer(
        string="Corrections go back", default=14,
        config_parameter='fm_attendance_correction.days_back',
        help="How many days into the past an employee may file a correction for. 0 removes the limit.")
    fm_ac_require_hr = fields.Boolean(
        string="HR validates after the manager", default=True,
        config_parameter='fm_attendance_correction.require_hr',
        help="Off: the manager's approval writes the attendance straight away.")
