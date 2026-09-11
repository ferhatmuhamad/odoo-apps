# -*- coding: utf-8 -*-
"""A purchase request, written from the requester's side of the desk.

The person who opens this most often is not a buyer. They do not know
product codes, they have no access to the Purchase app, and what they want
to know is simply "where is my request now". So a request here is a plain
list of things in the requester's own words, an approval by their own
manager, and a state that tells them what happened - all the way to
"it has arrived".

Purchasing turns those words into products and purchase orders, in one
step, from the request itself.
"""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Waiting Approval'),
    ('to_validate', 'Waiting Validation'),
    ('approved', 'Approved'),
    ('ordered', 'Ordered'),
    ('received', 'Received'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]

# States from which a requester may still take the request back.
CANCELLABLE_BY_REQUESTER = ('draft', 'submitted', 'to_validate')


class PurchaseRequest(models.Model):
    _name = 'fm.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Reference', default=lambda self: _('New'), copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    requester_id = fields.Many2one(
        'hr.employee', string='Requested by', required=True, tracking=True,
        default=lambda self: self.env.user.employee_id, check_company=True)
    user_id = fields.Many2one(
        'res.users', string='Requester user', compute='_compute_from_requester', store=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', compute='_compute_from_requester', store=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Approver', compute='_compute_from_requester', store=True,
        readonly=False, tracking=True,
        help="The requester's manager. Purchase managers may change it.")
    # Kept flat on purpose: the record rule that lets an approver see the
    # request compares this, and a rule that walked into hr.employee would
    # depend on the approver's rights on that model.
    approver_user_id = fields.Many2one(
        'res.users', string='Approver user', compute='_compute_approver_user', store=True)

    date_request = fields.Date(string='Request date', default=fields.Date.context_today, readonly=True)
    date_needed = fields.Date(string='Needed by', tracking=True)
    priority = fields.Selection([('0', 'Normal'), ('1', 'Urgent')], default='0', tracking=True)
    purpose = fields.Text(
        string='What is it for?', required=True,
        help='One or two sentences. This is what the approver reads first.')

    line_ids = fields.One2many('fm.purchase.request.line', 'request_id', string='Items', copy=True)
    amount_estimated = fields.Monetary(
        string='Estimated total', compute='_compute_amount', store=True, currency_field='currency_id')

    state = fields.Selection(
        STATES, default='draft', required=True, tracking=True, copy=False,
        group_expand='_group_expand_state')
    purchase_state = fields.Selection([
        ('none', 'Not ordered'),
        ('partial', 'Partially ordered'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
    ], compute='_compute_purchase_state', store=True)
    reject_reason = fields.Text(readonly=True, copy=False)

    # The trail a printed request needs: who did what, when.
    date_submitted = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False)
    date_approved = fields.Datetime(readonly=True, copy=False)
    validated_by_id = fields.Many2one('res.users', string='Validated by', readonly=True, copy=False)
    date_validated = fields.Datetime(readonly=True, copy=False)
    rejected_by_id = fields.Many2one('res.users', string='Rejected by', readonly=True, copy=False)
    date_rejected = fields.Datetime(readonly=True, copy=False)

    # Purchasing only: assigning a computed many2many is checked against the
    # comodel's access rights (19.0 does; earlier versions let it pass), and
    # the requester has none on purchase.order. Their view of the orders is
    # the two fields below, computed on their own.
    purchase_order_ids = fields.Many2many(
        'purchase.order', compute='_compute_purchase_orders', string='Purchase Orders',
        groups='purchase.group_purchase_user')
    purchase_count = fields.Integer(compute='_compute_purchase_info')
    purchase_order_names = fields.Char(compute='_compute_purchase_info', string='Order numbers')

    # What the current user may do, so the buttons can be honest.
    can_approve = fields.Boolean(compute='_compute_permissions')
    can_validate = fields.Boolean(compute='_compute_permissions')
    can_purchase = fields.Boolean(compute='_compute_permissions')
    is_requester = fields.Boolean(compute='_compute_permissions')

    @api.model
    def _group_expand_state(self, values, domain, *args):
        """Kanban columns in the order of the flow, not of the alphabet.

        Grouping by a selection sorts the groups by their database key, so
        'approved' came before 'draft'. Only the states that actually have
        requests are returned: a requester with two requests does not need
        eight columns. (`*args`: 17.0 also passes `order`; 18.0 does not.)"""
        present = set(values or [])
        return [key for key, _label in STATES if key in present]

    # ── Computes ─────────────────────────────────────────────────────────

    @api.depends('requester_id')
    def _compute_from_requester(self):
        for req in self:
            emp = req.requester_id
            req.user_id = emp.user_id
            req.department_id = emp.department_id
            req.manager_id = emp.parent_id

    @api.depends('manager_id.user_id')
    def _compute_approver_user(self):
        for req in self:
            req.approver_user_id = req.manager_id.user_id

    @api.depends('line_ids.amount_estimated', 'line_ids.is_cancelled')
    def _compute_amount(self):
        for req in self:
            req.amount_estimated = sum(req.line_ids.filtered(lambda l: not l.is_cancelled).mapped('amount_estimated'))

    @api.depends('line_ids.qty_ordered', 'line_ids.qty_received', 'line_ids.product_qty', 'line_ids.is_cancelled')
    def _compute_purchase_state(self):
        for req in self:
            lines = req.line_ids.filtered(lambda l: not l.is_cancelled)
            if not lines or not any(lines.mapped('qty_ordered')):
                req.purchase_state = 'none'
            elif all(l.qty_received >= l.product_qty for l in lines):
                req.purchase_state = 'received'
            elif all(l.qty_ordered >= l.product_qty for l in lines):
                req.purchase_state = 'ordered'
            else:
                req.purchase_state = 'partial'

    def _fm_orders(self):
        self.ensure_one()
        return self.sudo().line_ids.purchase_line_ids.order_id

    @api.depends('line_ids.purchase_line_ids.order_id')
    def _compute_purchase_orders(self):
        for req in self:
            req.purchase_order_ids = req._fm_orders()

    @api.depends('line_ids.purchase_line_ids.order_id')
    def _compute_purchase_info(self):
        # sudo inside: the requester cannot read purchase orders, yet the
        # number of them and their names are theirs to see.
        for req in self:
            orders = req._fm_orders()
            req.purchase_count = len(orders)
            req.purchase_order_names = ', '.join(orders.mapped('name'))

    @api.depends_context('uid')
    @api.depends('state', 'approver_user_id', 'user_id')
    def _compute_permissions(self):
        user = self.env.user
        purchase_user = user.has_group('purchase.group_purchase_user')
        purchase_manager = user.has_group('purchase.group_purchase_manager')
        for req in self:
            req.is_requester = req.user_id == user
            req.can_approve = req.state == 'submitted' and (
                req.approver_user_id == user or purchase_manager)
            req.can_validate = req.state == 'to_validate' and purchase_manager
            req.can_purchase = req.state in ('approved', 'ordered') and purchase_user

    # ── CRUD ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fm.purchase.request') or _('New')
        requests = super().create(vals_list)
        for req in requests:
            if req.user_id:
                req.message_subscribe(partner_ids=req.user_id.partner_id.ids)
        return requests

    def unlink(self):
        for req in self:
            if req.state not in ('draft', 'cancelled'):
                raise UserError(_('Only draft or cancelled requests can be deleted. %s is %s.',
                                  req.name, dict(STATES)[req.state]))
        return super().unlink()

    # ── Settings ─────────────────────────────────────────────────────────

    @api.model
    def _validation_threshold(self):
        """Above this estimated total a purchase manager must also validate.
        Zero means never."""
        try:
            return float(self.env['ir.config_parameter'].sudo().get_param(
                'fm_purchase_request.validation_threshold', '0') or 0)
        except ValueError:
            return 0.0

    # ── Workflow ─────────────────────────────────────────────────────────

    def _ensure(self, condition, message):
        if not condition:
            raise AccessError(message)

    def _post(self, body, partner_ids=None):
        """message_post that a user without an email address can call.

        Odoo refuses to post anything on behalf of a user whose partner has
        no email - and the requester is exactly the person most likely to
        log in as "rina" rather than as an address. A sender address from
        the company stands in, so the message (and the email to whoever
        follows the request) still goes out."""
        self.ensure_one()
        kwargs = {'body': body}
        if partner_ids:
            kwargs.update(partner_ids=partner_ids, message_type='comment', subtype_xmlid='mail.mt_comment')
        author = self.env.user.partner_id
        if not author.email:
            kwargs['email_from'] = '"%s" <%s>' % (
                author.name, self.env.company.email or 'noreply@%s' % (
                    self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain') or 'localhost'))
        return self.message_post(**kwargs)

    def _notify_requester(self, body):
        """A message the requester is sure to see: in their inbox, and by
        email if that is how they read Odoo."""
        self.ensure_one()
        return self._post(body, partner_ids=self.user_id.partner_id.ids)

    def action_submit(self):
        for req in self:
            self._ensure(req.is_requester or self.env.user.has_group('purchase.group_purchase_user'),
                         _('Only the requester can submit this request.'))
            if req.state != 'draft':
                raise UserError(_('%s has already been submitted.', req.name))
            if not req.line_ids.filtered(lambda l: not l.is_cancelled):
                raise UserError(_('Add at least one item before submitting.'))
            req.date_submitted = fields.Datetime.now()
            if req.approver_user_id:
                req.state = 'submitted'
                req._schedule_approval_activity()
            else:
                # Nobody above them with a login: a purchase manager decides.
                req.state = 'to_validate'
                req._post(_('No approver with a user account; waiting for a purchase manager to validate.'))
        return True

    def _schedule_approval_activity(self):
        """An activity for the approver - with the email Odoo sends for it
        when it can. A requester whose user has no email address makes
        Odoo refuse to send that email; the activity itself is still the
        point, so it is created without the email rather than not at all."""
        self.ensure_one()
        vals = dict(
            user_id=self.approver_user_id.id,
            summary=_('Approve purchase request %s', self.name),
            note=_('%(who)s asks for: %(what)s (estimated %(amount)s).',
                   who=self.requester_id.name, what=self.purpose, amount=self._fmt_amount()))
        try:
            with self.env.cr.savepoint():
                self.activity_schedule('mail.mail_activity_data_todo', **vals)
        except UserError:
            self.with_context(mail_activity_quick_update=True).activity_schedule(
                'mail.mail_activity_data_todo', **vals)

    def action_approve(self):
        for req in self:
            self._ensure(req.can_approve, _('Only the approver of %s can approve it.', req.name))
            req.activity_ids.filtered(lambda a: a.user_id == self.env.user).action_feedback(
                feedback=_('Approved'))
            req.write({'approved_by_id': self.env.uid, 'date_approved': fields.Datetime.now()})
            threshold = req._validation_threshold()
            if threshold and req.amount_estimated > threshold:
                req.state = 'to_validate'
                req._post(_(
                    'Approved by %(who)s. The estimated total (%(amount)s) is above %(limit)s, '
                    'so a purchase manager must validate it as well.',
                    who=self.env.user.name, amount=req._fmt_amount(),
                    limit=req._fmt_amount(threshold)))
            else:
                req._set_approved()
        return True

    def action_validate(self):
        for req in self:
            self._ensure(req.can_validate, _('Only a purchase manager can validate %s.', req.name))
            req.write({'validated_by_id': self.env.uid, 'date_validated': fields.Datetime.now()})
            req._set_approved()
        return True

    def _set_approved(self):
        self.ensure_one()
        self.state = 'approved'
        self._notify_requester(_('Your request %s has been approved and handed to purchasing.', self.name))

    def action_reject(self):
        """Opens the wizard; the reason is not optional."""
        self.ensure_one()
        self._ensure(self.can_approve or self.can_validate or self.can_purchase,
                     _('You cannot reject %s.', self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject %s', self.name),
            'res_model': 'fm.purchase.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def _do_reject(self, reason):
        self.ensure_one()
        self.activity_ids.action_feedback(feedback=_('Rejected'))
        self.write({
            'state': 'rejected', 'reject_reason': reason,
            'rejected_by_id': self.env.uid, 'date_rejected': fields.Datetime.now(),
        })
        self._notify_requester(_('Your request %(name)s was rejected by %(who)s: %(why)s',
                                 name=self.name, who=self.env.user.name, why=reason))

    def action_cancel(self):
        for req in self:
            allowed = (req.is_requester and req.state in CANCELLABLE_BY_REQUESTER) or (
                self.env.user.has_group('purchase.group_purchase_manager') and req.state not in ('ordered', 'received'))
            self._ensure(allowed, _('%s can no longer be cancelled.', req.name))
            req.activity_ids.unlink()
            req.state = 'cancelled'
        return True

    def action_draft(self):
        for req in self:
            self._ensure(req.is_requester or self.env.user.has_group('purchase.group_purchase_manager'),
                         _('Only the requester can reopen %s.', req.name))
            if req.state not in ('rejected', 'cancelled'):
                raise UserError(_('Only rejected or cancelled requests can be reopened.'))
            req.write({
                'state': 'draft', 'reject_reason': False, 'date_submitted': False,
                'approved_by_id': False, 'date_approved': False,
                'validated_by_id': False, 'date_validated': False,
                'rejected_by_id': False, 'date_rejected': False,
            })
        return True

    def action_make_purchase_order(self):
        self._ensure(self.env.user.has_group('purchase.group_purchase_user'),
                     _('Only purchasing can create purchase orders.'))
        for req in self:
            if req.state not in ('approved', 'ordered'):
                raise UserError(_('%s is not approved.', req.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Orders'),
            'res_model': 'fm.purchase.request.make.po',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids},
        }

    def action_receive(self):
        """The requester says it arrived. The last word is theirs, whatever
        the receipts say: a delivered box that is the wrong thing is not a
        fulfilled request."""
        for req in self:
            self._ensure(req.is_requester or self.env.user.has_group('purchase.group_purchase_user'),
                         _('Only the requester can confirm receipt of %s.', req.name))
            if req.state != 'ordered':
                raise UserError(_('%s has not been ordered yet.', req.name))
            req.state = 'received'
            req._post(_('Marked as received by %s.', self.env.user.name))
        return True

    def _after_ordered(self, orders):
        """Called by the wizard once purchase orders exist for this request."""
        self.ensure_one()
        links = ', '.join(
            '<a href="#" data-oe-model="purchase.order" data-oe-id="%d">%s</a>' % (o.id, o.name)
            for o in orders)
        if self.purchase_state in ('ordered', 'received') and self.state == 'approved':
            self.state = 'ordered'
            self._notify_requester(_('Your request %(name)s has been ordered: %(orders)s',
                                     name=self.name, orders=links))
        else:
            self._post(_('Purchase order(s) created for part of this request: %s', links))

    # ── Smart buttons ────────────────────────────────────────────────────

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')
        orders = self._fm_orders()
        if len(orders) == 1:
            action.update(views=[(False, 'form')], res_id=orders.id)
        else:
            action['domain'] = [('id', 'in', orders.ids)]
        action['context'] = {'create': 0}
        return action

    # ── Helpers ──────────────────────────────────────────────────────────

    def _fmt_amount(self, amount=None):
        self.ensure_one()
        from odoo.tools.misc import formatLang
        return formatLang(self.env, self.amount_estimated if amount is None else amount,
                          currency_obj=self.currency_id)
