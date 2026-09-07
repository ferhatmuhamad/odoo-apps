# Quick Notes

A lightweight place to keep short personal reminders inside Odoo.

Every user gets a private notebook: notes you create are visible only to you,
while a *Quick Notes / Administrator* can review all of them.

## Features

- Kanban, list and form views
- Tags with colours
- Three priority levels (Normal, Important, Urgent)
- Optional deadline, with overdue notes highlighted in red
- Pin the notes that matter most
- Archive instead of delete

## Compatibility

| Odoo | Branch |
|---|---|
| 19.0 | `19.0` |
| 18.0 | `18.0` |
| 17.0 | `17.0` |

Depends on `base` only, so it runs on both Odoo Community and Odoo Enterprise.

## Installation

1. Copy `fm_quick_note` into your Odoo `addons_path`.
2. Restart Odoo, then **Apps → Update Apps List**.
3. Install **Quick Notes**.

## Security groups

| Group | Can do |
|---|---|
| Quick Notes / User | Full access to their own notes; read-only on tags |
| Quick Notes / Administrator | Access to every user's notes; manages tags |

## License

LGPL-3
