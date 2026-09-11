# -*- coding: utf-8 -*-
"""The other end of the link: order lines know which request item they
fulfil, and orders can jump back to the requests they came from."""

from odoo import api, fields, models, _


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    fm_request_line_id = fields.Many2one(
        'fm.purchase.request.line', string='Request item', ondelete='set null', index=True, copy=False)
    fm_request_id = fields.Many2one(
        related='fm_request_line_id.request_id', string='Purchase Request', store=True)

    def _fm_uom(self):
        """The line's unit, whatever this version calls the field."""
        return self.product_uom


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    fm_request_ids = fields.Many2many(
        'fm.purchase.request', compute='_compute_fm_requests', string='Purchase Requests')
    fm_request_count = fields.Integer(compute='_compute_fm_requests')

    @api.depends('order_line.fm_request_id')
    def _compute_fm_requests(self):
        for order in self:
            requests = order.order_line.fm_request_id
            order.fm_request_ids = requests
            order.fm_request_count = len(requests)

    def action_view_fm_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('fm_purchase_request.action_purchase_request_all')
        requests = self.fm_request_ids
        if len(requests) == 1:
            action.update(views=[(False, 'form')], res_id=requests.id)
        else:
            action['domain'] = [('id', 'in', requests.ids)]
        return action

    def button_confirm(self):
        res = super().button_confirm()
        # The requester hears about it the moment the order is real.
        for order in self:
            for req in order.fm_request_ids:
                req._notify_requester(_(
                    'Purchase order %(po)s for your request %(name)s has been confirmed with %(vendor)s.',
                    po=order.name, name=req.name, vendor=order.partner_id.name))
        return res
