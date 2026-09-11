{
    'name': 'Attendance Geofence',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Office radius on every work location, a map on every check-in, and a policy for people outside it',
    'description': """
Attendance Geofence
===================

Draw a circle around each office. Every check-in and check-out Odoo records
is then judged against it - **In area**, **Out of area**, or **No position**
- with the distance, a map, and what to do about it.

Built on what Odoo already has
------------------------------
Odoo records GPS coordinates on every check-in from the systray and the
kiosk. Odoo already knows the places people work: *Work Locations*, linked
to every employee. This module adds a radius to those locations and judges
the coordinates Odoo already stores. No second list of offices, no second
GPS capture, and the geofence follows an employee the moment HR moves them
to another branch.

Many offices
------------
Any number of work locations can carry a geofence. An employee is checked
against their work location plus any others they are allowed at, and a
check-in inside any of them counts as In area. People whose work is not at
a fixed address can be exempted.

A policy per location
---------------------
Each location decides what happens to someone outside its radius:

* **Record and flag** - the check-in succeeds and is marked Out of area.
* **Ask for a reason** - the check-in succeeds once the person has typed why.
* **Block** - the check-in is refused, with the distance in the message.

The rule is enforced on the server, at the one method every check-in goes
through, so nothing in a browser can get around it.

Positions that look wrong
-------------------------
An accuracy of exactly 0 m, a position minutes old, a device reporting
highway speeds, or a check-in that would have needed 400 km/h to reach from
the previous check-out - each is flagged with a note saying why. Flagged, not
refused: the decision stays with HR.

Seeing it
---------
A map on every attendance with the person, the office, the circle and the
distance. A map of the day with every check-in and every office at once. A
report by location with counts of In area / Out of area, in list and pivot.

Kiosk
-----
Check-ins from the kiosk are judged and mapped like any other. Because a
kiosk is a shared device standing where HR put it, it does not ask for
reasons, and "Block" only applies when the kiosk actually has a position.

Everything lives on Odoo's own models - work locations, employees,
attendances - so there is nothing to migrate and nothing to lose on
uninstall.
""",
    'author': 'Ferhat Muhamad',
    'maintainer': 'Ferhat Muhamad',
    'website': 'https://github.com/ferhatmuhamad',
    'support': 'ferhatmuhamad221@gmail.com',
    'license': 'LGPL-3',
    'depends': ['hr_attendance'],
    'data': [
        'views/hr_work_location_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Leaflet (BSD-2, vendored): see static/lib/leaflet/LICENSE.
            'fm_attendance_geo/static/lib/leaflet/leaflet.css',
            'fm_attendance_geo/static/lib/leaflet/leaflet.js',
            'fm_attendance_geo/static/src/scss/geo.scss',
            'fm_attendance_geo/static/src/js/leaflet_map.js',
            'fm_attendance_geo/static/src/js/geo_map_field.js',
            'fm_attendance_geo/static/src/xml/geo_map_field.xml',
            'fm_attendance_geo/static/src/js/geo_reason_dialog.js',
            'fm_attendance_geo/static/src/xml/geo_reason_dialog.xml',
            'fm_attendance_geo/static/src/js/attendance_menu_patch.js',
            'fm_attendance_geo/static/src/js/day_map_action.js',
            'fm_attendance_geo/static/src/xml/day_map_action.xml',
        ],
    },
    'images': [
        'static/description/images/main_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
