# -*- coding: utf-8 -*-
from odoo import api, fields, models

PARAM = 'fm_sales_scoreboard.'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_sb_refresh_seconds = fields.Integer(
        string='Refresh every (s)', default=15, config_parameter=PARAM + 'refresh_seconds',
        help='How often the board fetches fresh figures.')
    fm_sb_slide_seconds = fields.Integer(
        string='Next salesperson every (s)', default=10, config_parameter=PARAM + 'slide_seconds')
    fm_sb_target = fields.Float(
        string='Monthly target per salesperson', default=0.0, config_parameter=PARAM + 'target',
        help='Closed value each salesperson is expected to reach in a month. Zero: no target, '
             'and the achievement figure is not shown.')
    fm_sb_won_stage_ids = fields.Many2many(
        'crm.stage', 'fm_sb_won_stage_rel', string='Won stages',
        help='Stages that count as won. Empty: every stage marked "Is Won" in CRM.')
    fm_sb_user_ids = fields.Many2many(
        'res.users', 'fm_sb_user_rel', string='Salespersons on the board',
        domain="[('share', '=', False)]",
        help='Empty: everyone who owns a lead in the current companies.')
    fm_sb_creator_ids = fields.Many2many(
        'res.users', 'fm_sb_creator_rel', string='"Created by" choices',
        domain="[('share', '=', False)]",
        help='Users offered in the "Created by" filter. Empty: everyone who has created a lead.')

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()

        def ids(key):
            raw = icp.get_param(PARAM + key) or ''
            return [int(x) for x in raw.split(',') if x.strip().isdigit()]

        res.update(
            fm_sb_won_stage_ids=[(6, 0, self.env['crm.stage'].browse(ids('won_stage_ids')).exists().ids)],
            fm_sb_user_ids=[(6, 0, self.env['res.users'].browse(ids('user_ids')).exists().ids)],
            fm_sb_creator_ids=[(6, 0, self.env['res.users'].browse(ids('creator_ids')).exists().ids)],
        )
        return res

    def set_values(self):
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM + 'won_stage_ids', ','.join(map(str, self.fm_sb_won_stage_ids.ids)))
        icp.set_param(PARAM + 'user_ids', ','.join(map(str, self.fm_sb_user_ids.ids)))
        icp.set_param(PARAM + 'creator_ids', ','.join(map(str, self.fm_sb_creator_ids.ids)))
