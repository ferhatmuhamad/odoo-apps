from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestHomeGridTour(HttpCase):
    """Runs the launcher in a real browser.

    Unit tests cannot reach this module at all: everything it does lives in
    OWL components and SCSS. A browser tour is the only way to prove the
    button appears, the overlay opens and searching works.
    """

    def test_home_grid_tour(self):
        self.start_tour('/odoo', 'fm_home_grid_tour', login='admin')
