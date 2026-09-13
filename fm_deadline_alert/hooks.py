# -*- coding: utf-8 -*-
"""Seed deadline sources for the models that happen to be installed.

The module depends on nothing but mail and bus; whether a company has
Project, CRM, Sales or Purchase is their business. Whatever is there when
this module is installed gets a source; anything installed later can be
added from Settings in a minute.
"""

SEEDS = [
    # model, label, date field, assignee field, only-open domain, icon
    ('project.task', 'Task deadline', 'date_deadline', 'user_ids',
     "[('state', 'not in', ['1_done', '1_canceled'])]", 'fa-tasks'),
    ('crm.lead', 'Expected closing', 'date_deadline', 'user_id',
     "[('active', '=', True), ('probability', '<', 100)]", 'fa-star'),
    ('sale.order', 'Quotation expiry', 'validity_date', 'user_id',
     "[('state', 'in', ['draft', 'sent'])]", 'fa-file-text-o'),
    ('purchase.order', 'Order deadline', 'date_order', 'user_id',
     "[('state', 'in', ['draft', 'sent'])]", 'fa-shopping-cart'),
    ('account.move', 'Invoice due', 'invoice_date_due', 'invoice_user_id',
     "[('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])]",
     'fa-money'),
]


def seed_sources(env):
    """Idempotent: adds a source for each seeded model that is installed
    and not yet covered. Called on install AND every time the registry is
    loaded (see fm.deadline.source._register_hook), so an app installed
    after this module - or in the same command, in whatever order - gets
    its source too."""
    Source = env['fm.deadline.source'].sudo().with_context(active_test=False)
    for model, label, date_field, user_field, domain, icon in SEEDS:
        if model not in env or date_field not in env[model]._fields or user_field not in env[model]._fields:
            continue
        if Source.search([('model_name', '=', model), ('date_field_name', '=', date_field)], limit=1):
            continue
        ir_model = env['ir.model']._get(model)
        Source.create({
            'name': label,
            'model_id': ir_model.id,
            'date_field_id': env['ir.model.fields']._get(model, date_field).id,
            'user_field_id': env['ir.model.fields']._get(model, user_field).id,
            'domain': domain,
            'icon': icon,
        })


def post_init_hook(env):
    seed_sources(env)
