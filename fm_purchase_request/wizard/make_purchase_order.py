# -*- coding: utf-8 -*-
"""Words into orders.

This is where a request written in plain language meets the catalogue.
Purchasing sees every open item, gives each a product and a vendor, and
one click makes the orders - one per vendor, or added to the vendor's
open RFQ so a week of small requests becomes one order instead of nine.
"""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _po_uom(product):
    """The unit a product is bought in: its purchase unit where the version
    still has one (17.0, 18.0), its unit otherwise (19.0)."""
    if 'uom_po_id' in product._fields and product.uom_po_id:
        return product.uom_po_id
    return product.uom_id


class MakePurchaseOrder(models.TransientModel):
    _name = 'fm.purchase.request.make.po'
    _description = 'Create Purchase Orders from Requests'

    request_ids = fields.Many2many('fm.purchase.request', string='Requests', readonly=True)
    line_ids = fields.One2many('fm.purchase.request.make.po.line', 'wizard_id', string='Items')
    merge_draft_po = fields.Boolean(
        string='Add to the vendor\'s open RFQ', default=True,
        help='If the vendor already has a draft RFQ in this company, add the lines to it '
             'instead of creating another order.')
    create_missing_products = fields.Boolean(
        string='Create products for items without one', default=False,
        help='For the one-off things nobody will buy again: a consumable named after the '
             'item is created, so the order can exist. Items that already have a product '
             'are left alone.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        Request = self.env['fm.purchase.request']
        if ctx.get('active_model') == 'fm.purchase.request':
            requests = Request.browse(ctx.get('active_ids') or [])
        elif ctx.get('active_model') == 'fm.purchase.request.line':
            requests = self.env['fm.purchase.request.line'].browse(ctx.get('active_ids') or []).request_id
        else:
            requests = Request
        requests = requests.filtered(lambda r: r.state in ('approved', 'ordered'))
        if not requests:
            raise UserError(_('Select at least one approved request.'))
        if len(requests.company_id) > 1:
            raise UserError(_('Select requests of one company at a time.'))
        lines = []
        for req in requests:
            for line in req.line_ids:
                if line.is_cancelled or line.qty_to_order <= 0:
                    continue
                lines.append((0, 0, {
                    'request_line_id': line.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.qty_to_order,
                    'product_uom_id': line.product_uom_id.id,
                    'price_unit': line.price_estimated,
                    'vendor_id': (line.vendor_id or line.product_id.seller_ids[:1].partner_id).id,
                }))
        if not lines:
            raise UserError(_('Every item of the selected requests has already been ordered.'))
        res.update(request_ids=[(6, 0, requests.ids)], line_ids=lines)
        return res

    def action_create(self):
        self.ensure_one()
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_('Only purchasing can create purchase orders.'))
        lines = self.line_ids.filtered(lambda l: l.product_qty > 0)
        if self.create_missing_products:
            for line in lines.filtered(lambda l: not l.product_id):
                line._create_product()
        missing = lines.filtered(lambda l: not l.product_id or not l.vendor_id)
        if missing:
            raise UserError(_('Choose a product and a vendor for: %s',
                              ', '.join(missing.mapped('name'))))
        if not lines:
            raise UserError(_('Nothing to order.'))

        company = self.request_ids.company_id
        Order = self.env['purchase.order']
        by_vendor = defaultdict(lambda: self.env['fm.purchase.request.make.po.line'])
        for line in lines:
            by_vendor[line.vendor_id] += line

        orders = Order
        touched = defaultdict(lambda: Order)
        for vendor, vlines in by_vendor.items():
            origin = ', '.join(sorted(set(vlines.request_line_id.request_id.mapped('name'))))
            order = Order
            if self.merge_draft_po:
                order = Order.search([
                    ('partner_id', '=', vendor.id), ('company_id', '=', company.id),
                    ('state', '=', 'draft'),
                ], order='id desc', limit=1)
                if order and order.origin and origin not in order.origin:
                    order.origin = '%s, %s' % (order.origin, origin)
                elif order and not order.origin:
                    order.origin = origin
            if not order:
                order = Order.create({
                    'partner_id': vendor.id,
                    'company_id': company.id,
                    'origin': origin,
                })
            for line in vlines:
                self.env['purchase.order.line'].create(line._prepare_po_line(order))
                line.request_line_id.write({
                    'product_id': line.product_id.id,
                    'vendor_id': vendor.id,
                })
            orders |= order
            for req in vlines.request_line_id.request_id:
                touched[req] |= order

        for req, req_orders in touched.items():
            req._after_ordered(req_orders)

        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')
        if len(orders) == 1:
            action.update(views=[(False, 'form')], res_id=orders.id)
        else:
            action['domain'] = [('id', 'in', orders.ids)]
        return action


class MakePurchaseOrderLine(models.TransientModel):
    _name = 'fm.purchase.request.make.po.line'
    _description = 'Create Purchase Orders from Requests - Item'

    wizard_id = fields.Many2one('fm.purchase.request.make.po', required=True, ondelete='cascade')
    request_line_id = fields.Many2one('fm.purchase.request.line', required=True, readonly=True)
    request_id = fields.Many2one(related='request_line_id.request_id')
    name = fields.Char(related='request_line_id.name', string='Requested')
    requester_id = fields.Many2one(related='request_line_id.request_id.requester_id')
    url = fields.Char(related='request_line_id.url')
    company_id = fields.Many2one(related='request_line_id.company_id')
    currency_id = fields.Many2one(related='request_line_id.currency_id')

    product_id = fields.Many2one(
        'product.product', string='Product', check_company=True,
        domain="[('purchase_ok', '=', True)]")
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit')
    price_unit = fields.Monetary(string='Unit price', currency_field='currency_id',
                                 help='Left at zero, Odoo takes the price from the vendor pricelist.')
    vendor_id = fields.Many2one('res.partner', string='Vendor', check_company=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = _po_uom(line.product_id)
                if not line.vendor_id and line.product_id.seller_ids:
                    line.vendor_id = line.product_id.seller_ids[0].partner_id

    def _prepare_po_line(self, order):
        self.ensure_one()
        vals = {
            'order_id': order.id,
            'product_id': self.product_id.id,
            # The requester's words stay on the order, so the vendor and
            # the receiver read the same thing the requester meant.
            'name': self.name,
            'product_qty': self.product_qty,
            'fm_request_line_id': self.request_line_id.id,
        }
        if self.product_uom_id:
            vals['product_uom'] = self.product_uom_id.id
        if self.price_unit:
            vals['price_unit'] = self.price_unit
        return vals

    def _create_product(self):
        """For the one-off thing nobody will ever buy again: a consumable
        named after the item, so the order can exist."""
        self.ensure_one()
        if not self.name:
            raise UserError(_('The item has no description to name a product after.'))
        # sudo: a buyer may not create products in Odoo's default rights,
        # yet a one-off consumable for an order they are placing is their
        # job. Scoped to their own company.
        Product = self.env['product.product'].sudo()
        uom = self.product_uom_id.id or self.env.ref('uom.product_uom_unit').id
        vals = {
            'name': self.name,
            'detailed_type': 'consu',
            'purchase_ok': True,
            'sale_ok': False,
            'uom_id': uom,
            'standard_price': self.price_unit,
            'company_id': self.company_id.id,
        }
        # The purchase unit went away with the UoM overhaul in 19.0.
        if 'uom_po_id' in Product._fields:
            vals['uom_po_id'] = uom
        product = Product.create(vals)
        self.product_id = product.id
        return product
