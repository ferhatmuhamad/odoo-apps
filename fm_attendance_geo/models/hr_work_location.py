# -*- coding: utf-8 -*-
"""A geofence is a property of a work location, not a model of its own.

Odoo already has the notion of "the places people work": hr.work.location,
linked to every employee. Putting the circle there means a company with five
branches configures five things it already had, and the geofence follows an
employee the moment HR moves them to another branch.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from . import geo

POLICIES = [
    ('record', 'Record and flag'),
    ('reason', 'Ask for a reason'),
    ('block', 'Block the check-in'),
]


class HrWorkLocation(models.Model):
    _inherit = 'hr.work.location'

    fm_geo_enabled = fields.Boolean(
        string='Geofence', default=False,
        help='Compare every check-in and check-out against this location.')
    fm_geo_latitude = fields.Float(string='Latitude', digits=(10, 7))
    fm_geo_longitude = fields.Float(string='Longitude', digits=(10, 7))
    fm_geo_radius = fields.Integer(
        string='Radius (m)', default=lambda self: self._fm_geo_default_radius(),
        help='How far from the pin still counts as being here. Consumer GPS is '
             'good to 5-20 m in the open and much worse indoors, so anything '
             'under about 50 m will flag people who are standing at their desk.')
    fm_geo_policy = fields.Selection(
        POLICIES, string='Outside the area', default='record', required=True,
        help='What happens when someone checks in from outside this radius.\n'
             '- Record and flag: the check-in succeeds and is marked Out of Area.\n'
             '- Ask for a reason: the check-in succeeds once a reason is given.\n'
             '- Block: the check-in is refused.\n'
             'When an employee is outside all of their locations, the policy of '
             'the nearest one applies.')
    # readonly=False on purpose: a computed field is readonly to the form
    # unless told otherwise, and the map widget on it must be clickable.
    # Nothing is ever written to this field - the widget writes latitude
    # and longitude - so no inverse is needed.
    fm_geo_map = fields.Json(compute='_compute_fm_geo_map', readonly=False)

    @api.model
    def _fm_geo_default_radius(self):
        value = self.env['ir.config_parameter'].sudo().get_param('fm_attendance_geo.default_radius')
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            return 100

    @api.depends('fm_geo_latitude', 'fm_geo_longitude', 'fm_geo_radius', 'name')
    def _compute_fm_geo_map(self):
        # What the map widget on the form needs, in one place, so the widget
        # does not have to know the names of four other fields.
        for loc in self:
            loc.fm_geo_map = {
                'lat': loc.fm_geo_latitude,
                'lng': loc.fm_geo_longitude,
                'radius': loc.fm_geo_radius,
                'name': loc.name,
                'has_point': geo.valid(loc.fm_geo_latitude, loc.fm_geo_longitude),
            }

    @api.constrains('fm_geo_enabled', 'fm_geo_latitude', 'fm_geo_longitude', 'fm_geo_radius')
    def _check_fm_geo(self):
        for loc in self:
            if not (-90.0 <= loc.fm_geo_latitude <= 90.0):
                raise ValidationError(_(
                    'The latitude of %(name)s is %(value)s; it must be between -90 and 90. '
                    'Use a dot as the decimal separator.',
                    name=loc.name, value=loc.fm_geo_latitude))
            if not (-180.0 <= loc.fm_geo_longitude <= 180.0):
                raise ValidationError(_(
                    'The longitude of %(name)s is %(value)s; it must be between -180 and 180. '
                    'Use a dot as the decimal separator.',
                    name=loc.name, value=loc.fm_geo_longitude))
            if loc.fm_geo_enabled:
                if not geo.valid(loc.fm_geo_latitude, loc.fm_geo_longitude):
                    raise ValidationError(_(
                        '%(name)s has a geofence but no position. Click the map, '
                        'or take the coordinates from its address.', name=loc.name))
                if loc.fm_geo_radius <= 0:
                    raise ValidationError(_(
                        'The radius of %(name)s must be greater than zero.', name=loc.name))

    def action_fm_geo_use_address(self):
        """Copy the coordinates Odoo already keeps on the address contact.

        `base_geolocalize` fills those with a Geolocate button; a company that
        has it gets the pin for free.
        """
        for loc in self:
            partner = loc.address_id
            if not geo.valid(partner.partner_latitude, partner.partner_longitude):
                raise UserError(_(
                    'The address "%(partner)s" has no coordinates yet. Either click the '
                    'map to place the pin, or set them on the contact (the Geolocate '
                    'button, with the base_geolocalize module installed).',
                    partner=partner.display_name or '-'))
            loc.write({
                'fm_geo_latitude': partner.partner_latitude,
                'fm_geo_longitude': partner.partner_longitude,
            })
        return True

    def _fm_geo_distance_to(self, lat, lng):
        self.ensure_one()
        return geo.distance_m(lat, lng, self.fm_geo_latitude, self.fm_geo_longitude)

    def _fm_geo_fence_snapshot(self):
        """The circle as it was when a verdict was reached. Stored on the
        attendance, because a pin that is moved next month must not rewrite
        the meaning of last month's check-ins."""
        self.ensure_one()
        return {
            'lat': self.fm_geo_latitude,
            'lng': self.fm_geo_longitude,
            'radius': self.fm_geo_radius,
            'name': self.name,
        }
