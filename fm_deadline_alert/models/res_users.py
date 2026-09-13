# -*- coding: utf-8 -*-
"""Odoo's own activity badge counts only today and overdue; with the
option on, planned activities count too, so the badge never reads zero
while there is work scheduled. 17.0 computes the groups in
systray_get_activities(); 18.0 and later in _get_activity_groups().
Both are covered; the one this version does not call is never reached."""

from odoo import api, models

PARAM = 'fm_deadline_alert.count_planned'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _fm_count_planned(self, groups):
        if (self.env['ir.config_parameter'].sudo().get_param(PARAM, 'True') or 'True') != 'True':
            return groups
        for group in groups:
            group['total_count'] = (group.get('overdue_count', 0) + group.get('today_count', 0)
                                    + group.get('planned_count', 0))
        return groups

    @api.model
    def systray_get_activities(self):
        return self._fm_count_planned(super().systray_get_activities())

    @api.model
    def _get_activity_groups(self):
        return self._fm_count_planned(super()._get_activity_groups())
