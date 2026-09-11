# -*- coding: utf-8 -*-
"""One thing the requester needs, in their own words.

`name` is the whole point: a requester writes "HDMI cable, 2 m, for the
meeting room" and is done. A product is optional here and required only
when purchasing makes the order - that is where the catalogue gets
involved, not before.
"""

from odoo import api, fields, models


class PurchaseRequestLine(models.Model):
    _name = 'fm.purchase.request.line'
    _description = 'Purchase Request Item'
    _order = 'request_id, sequence, id'
    _check_company_auto = True

    request_id = fields.Many2one('fm.purchase.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    state = fields.Selection(related='request_id.state', store=True)
    sequence = fields.Integer(default=10)

    name = fields.Char(string='Item', required=True,
                       help='Describe it the way you would to a colleague.')
    product_id = fields.Many2one(
        'product.product', string='Product', check_company=True,
        domain="[('purchase_ok', '=', True)]",
        help='Optional. Purchasing picks the product when ordering.')
    product_qty = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit', default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False))
    price_estimated = fields.Monetary(string='Est. unit price', currency_field='currency_id')
    amount_estimated = fields.Monetary(
        string='Est. amount', compute='_compute_amount', store=True, currency_field='currency_id')
    url = fields.Char(string='Link', help='Where you saw it, if anywhere.')
    vendor_id = fields.Many2one(
        'res.partner', string='Suggested vendor', check_company=True,
        domain="[('is_company', '=', True)]")

    # Purchasing may drop an item without rejecting the whole request.
    is_cancelled = fields.Boolean(string='Dropped', copy=False)
    cancel_note = fields.Char(string='Why dropped', copy=False)

    purchase_line_ids = fields.One2many('purchase.order.line', 'fm_request_line_id', string='Order lines', copy=False)
    qty_ordered = fields.Float(compute='_compute_quantities', store=True, digits='Product Unit of Measure')
    qty_received = fields.Float(compute='_compute_quantities', store=True, digits='Product Unit of Measure')
    purchase_state = fields.Selection([
        ('none', 'Not ordered'), ('partial', 'Partial'), ('ordered', 'Ordered'), ('received', 'Received'),
    ], compute='_compute_quantities', store=True)

    @api.depends('product_qty', 'price_estimated')
    def _compute_amount(self):
        for line in self:
            line.amount_estimated = line.product_qty * line.price_estimated

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                if not line.name:
                    line.name = line.product_id.display_name
                product = line.product_id
                line.product_uom_id = (product.uom_po_id if 'uom_po_id' in product._fields and product.uom_po_id
                                       else product.uom_id)
                if not line.price_estimated:
                    line.price_estimated = line.product_id.standard_price

    @api.depends('purchase_line_ids.product_qty', 'purchase_line_ids.qty_received',
                 'purchase_line_ids.order_id.state', 'product_qty', 'product_uom_id')
    def _compute_quantities(self):
        for line in self:
            ordered = received = 0.0
            # sudo: recomputed whenever the requester edits their quantity,
            # and the requester may not read order lines.
            for pol in line.sudo().purchase_line_ids.filtered(lambda l: l.order_id.state != 'cancel'):
                ordered += line._to_request_uom(pol, pol.product_qty)
                received += line._to_request_uom(pol, pol.qty_received)
            line.qty_ordered = ordered
            line.qty_received = received
            if not ordered:
                line.purchase_state = 'none'
            elif received >= line.product_qty:
                line.purchase_state = 'received'
            elif ordered >= line.product_qty:
                line.purchase_state = 'ordered'
            else:
                line.purchase_state = 'partial'

    def _to_request_uom(self, pol, qty):
        """Quantities on the order are in the order line's unit; the
        requester reads them in theirs. Converted when the units are
        convertible, taken as they are otherwise - Odoo decides which,
        because what makes two units convertible changed in 19.0
        (categories became a tree of reference units)."""
        po_uom = pol._fm_uom()
        if po_uom and self.product_uom_id and po_uom != self.product_uom_id:
            return po_uom._compute_quantity(qty, self.product_uom_id, round=False, raise_if_failure=False)
        return qty

    @property
    def qty_to_order(self):
        return max(self.product_qty - self.qty_ordered, 0.0)
