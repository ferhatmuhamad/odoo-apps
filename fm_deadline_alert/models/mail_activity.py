# -*- coding: utf-8 -*-
"""Whenever an activity of mine appears, moves, is done or is deleted, my
bell learns about it now - not on the next page load."""

from odoo import api, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _fm_refresh(self, users):
        if users:
            self.env['fm.deadline.alert']._notify_users(users)

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        self._fm_refresh(activities.user_id)
        return activities

    def write(self, vals):
        before = self.user_id
        res = super().write(vals)
        # 'active': 19.0 archives a done activity instead of deleting it,
        # and an archived one can be brought back.
        if (any(k in vals for k in ('user_id', 'date_deadline', 'summary', 'activity_type_id', 'res_id', 'res_model', 'active'))
                and not self.env.context.get('fm_deadline_alert_done')):
            self._fm_refresh(before | self.user_id)
        return res

    def unlink(self):
        users = self.user_id
        res = super().unlink()
        # Marking done unlinks (17.0, 18.0) or archives (19.0) too; that path
        # has already told everyone.
        if not self.env.context.get('fm_deadline_alert_done'):
            self._fm_refresh(users)
        return res

    def _action_done(self, feedback=False, attachment_ids=None):
        # Taken before super(): the records are gone (or archived) afterwards.
        users = self.user_id
        res = super(MailActivity, self.with_context(fm_deadline_alert_done=True))._action_done(
            feedback=feedback, attachment_ids=attachment_ids)
        self._fm_refresh(users)
        return res
