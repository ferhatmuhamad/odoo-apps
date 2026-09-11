# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_pr_validation_threshold = fields.Float(
        string='Validation above', default=0.0,
        config_parameter='fm_purchase_request.validation_threshold',
        help="Requests whose estimated total is above this amount need a purchase "
             "manager's validation after the manager's approval. Zero: never.")
