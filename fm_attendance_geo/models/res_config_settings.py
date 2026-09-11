# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fm_geo_default_radius = fields.Integer(
        string='Default radius (m)', default=100,
        config_parameter='fm_attendance_geo.default_radius',
        help='Proposed when a geofence is added to a work location.')
    fm_geo_tile_url = fields.Char(
        string='Map tiles', default='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        config_parameter='fm_attendance_geo.tile_url',
        help='Any XYZ tile server. The default is the public OpenStreetMap server, '
             'which is fine for an office and asks not to be used for heavy traffic; '
             'a company with hundreds of check-ins an hour should point this at its '
             'own provider.')
    fm_geo_tile_attribution = fields.Char(
        string='Tile attribution',
        default='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        config_parameter='fm_attendance_geo.tile_attribution')
    fm_geo_max_accuracy = fields.Integer(
        string='Flag accuracy worse than (m)', default=500,
        config_parameter='fm_attendance_geo.max_accuracy')
    fm_geo_max_age_min = fields.Integer(
        string='Flag positions older than (min)', default=5,
        config_parameter='fm_attendance_geo.max_age_min')
    fm_geo_max_speed_kmh = fields.Integer(
        string='Flag speeds above (km/h)', default=150,
        config_parameter='fm_attendance_geo.max_speed_kmh',
        help='Applied both to the speed the device reports and to the speed implied '
             'by the distance from the previous check-in or check-out.')
