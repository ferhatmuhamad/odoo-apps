# -*- coding: utf-8 -*-
"""Refusing takes a reason. A correction turned down without one just comes
back tomorrow as the same question."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class AttendanceCorrectionRefuse(models.TransientModel):
    _name = 'fm.attendance.correction.refuse'
    _description = "Refuse an Attendance Correction"

    request_id = fields.Many2one('fm.attendance.correction', required=True, ondelete='cascade')
    reason = fields.Text(string="Why", required=True)

    def action_refuse(self):
        self.ensure_one()
        request = self.request_id
        if not request.can_refuse:
            raise AccessError(_("You cannot refuse this request."))
        request.sudo().write({
            'state': 'refused',
            'refused_by': self.env.user.id,
            'refuse_reason': self.reason,
        })
        request.activity_unlink(['mail.mail_activity_data_todo'])
        user = request.employee_id.sudo().user_id
        request.sudo().message_post(
            body=_("Refused by %(who)s: %(why)s", who=self.env.user.name, why=self.reason),
            partner_ids=user.partner_id.ids if user else None)
        return {'type': 'ir.actions.act_window_close'}
