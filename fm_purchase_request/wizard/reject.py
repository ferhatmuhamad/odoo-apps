# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseRequestReject(models.TransientModel):
    _name = 'fm.purchase.request.reject'
    _description = 'Reject a Purchase Request'

    request_id = fields.Many2one('fm.purchase.request', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True,
                         help='The requester reads this. Say what would make it approvable, if anything.')

    def action_confirm(self):
        self.ensure_one()
        self.request_id._do_reject(self.reason.strip())
        return {'type': 'ir.actions.act_window_close'}
