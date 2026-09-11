# -*- coding: utf-8 -*-
"""The one piece of arithmetic in this module, kept away from the models so
it can be tested on its own and never accidentally depend on a record."""

import math

# Mean Earth radius (IUGG). Good to ~0.3% anywhere, which at the scale of an
# office radius is centimetres.
EARTH_RADIUS_M = 6371008.8


def valid(lat, lng):
    """A pair of coordinates worth computing with.

    Odoo stores an unset Float as 0.0, so (0, 0) - a point in the Gulf of
    Guinea - is treated as "no position" rather than as a place. A real
    check-in there would be the least of anyone's problems.
    """
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return False
    if math.isnan(lat) or math.isnan(lng):
        return False
    if lat == 0 and lng == 0:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def distance_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
