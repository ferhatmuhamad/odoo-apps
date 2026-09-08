import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:  # optional: unlocks every country supported by the library
    import holidays as holidays_lib
except ImportError:  # pragma: no cover
    holidays_lib = None
    _logger.info(
        "Python library 'holidays' is not installed. "
        "Public Holiday Importer will use its bundled data only."
    )


class PublicHoliday(models.Model):
    _name = 'fm.public.holiday'
    _description = 'Public Holiday'
    _order = 'date desc, name'

    name = fields.Char(string='Holiday', required=True, translate=True)
    date = fields.Date(string='Date', required=True, index=True)
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        required=True,
        index=True,
        ondelete='cascade',
    )
    year = fields.Integer(
        string='Year',
        compute='_compute_year',
        store=True,
        index=True,
    )
    country_code = fields.Char(related='country_id.code', string='Code', store=True)

    _country_date_uniq = models.Constraint(
        'UNIQUE(country_id, date)',
        'This country already has a holiday recorded on that date.',
    )

    @api.depends('date')
    def _compute_year(self):
        for holiday in self:
            holiday.year = holiday.date.year if holiday.date else 0

    @api.model
    def _library_available(self):
        """Return True when the optional `holidays` package can be used."""
        return holidays_lib is not None

    @api.model
    def _library_country_codes(self):
        """Country codes the installed library can generate, or an empty list."""
        if not holidays_lib:
            return []
        return sorted(holidays_lib.list_supported_countries())

    @api.model
    def _fetch_from_library(self, country_code, year_from, year_to):
        """Generate holiday records for a country using the `holidays` package.

        Returns the number of newly created records.
        """
        if not holidays_lib:
            raise UserError(_(
                "The Python library 'holidays' is not installed on this server, "
                "so only the bundled countries are available.\n\n"
                "Ask your administrator to run:  pip install holidays"
            ))
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if not country:
            raise UserError(_("No country found with the code %s.", country_code))

        years = list(range(year_from, year_to + 1))
        try:
            found = holidays_lib.country_holidays(country_code, years=years)
        except NotImplementedError:
            raise UserError(_(
                "The 'holidays' library does not support %s yet.", country.name
            )) from None

        existing = set(self.search([
            ('country_id', '=', country.id),
            ('date', '>=', fields.Date.to_date('%s-01-01' % year_from)),
            ('date', '<=', fields.Date.to_date('%s-12-31' % year_to)),
        ]).mapped('date'))

        vals_list = []
        for day in sorted(found):
            if day.year not in years or day in existing:
                continue
            vals_list.append({
                'name': found[day],
                'date': day,
                'country_id': country.id,
            })
        if vals_list:
            self.create(vals_list)
        return len(vals_list)
