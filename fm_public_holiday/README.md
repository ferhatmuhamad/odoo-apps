# Public Holiday Importer

Add public holidays to your Odoo working schedules without typing a single date.

Odoo can already exclude public holidays from working time — but it never fills
them in for you. This module ships a reference list of holidays and copies the
ones you choose into your working schedules in one step.

---

## Table of contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [First use](#first-use)
4. [Features](#features)
5. [Bundled countries](#bundled-countries)
6. [Unlocking more countries](#unlocking-more-countries)
7. [Indonesia: a note on *cuti bersama*](#indonesia-a-note-on-cuti-bersama)
8. [How the dates are stored](#how-the-dates-are-stored)
9. [Security groups](#security-groups)
10. [Troubleshooting](#troubleshooting)
11. [Uninstalling](#uninstalling)
12. [Support](#support)

---

## Requirements

| | |
|---|---|
| Odoo | 17.0, 18.0 or 19.0 — Community or Enterprise |
| Depends on | `hr_holidays` (Time Off), which is part of Odoo Community |
| Extra Python packages | **None required.** `holidays` is optional — see below |

---

## Installation

1. Copy the `fm_public_holiday` folder into your Odoo `addons_path`.
2. Restart the Odoo service.
3. Go to **Apps**, click **Update Apps List**.
4. Remove the *Apps* filter, search for **Public Holiday Importer**, click **Install**.

After installation you will find a new **Public Holidays** app in the main menu.

> The module loads about 1,300 reference dates on install, so the first
> installation takes a few seconds longer than a typical module.

---

## First use

**Public Holidays → Import to Schedules**

### Step 1 — scope

1. **Countries** — pick one or several. Type to search, or use
   **Select all available** to take every country that has data. Remove a country
   by clicking the × on its tag, or **Clear** to start over.
2. **From Year / To Year** — the range you want. Defaults to the current year.
3. **Working Schedules** — leave empty to apply to *every* working schedule of the
   current company, or pick specific ones.
4. Click **Next: choose holidays**.

### Step 2 — pick the holidays you actually want

You now see every matching holiday, one line per date, all checked.

**Remove the line of any holiday you do not want.** A company that does not
observe Christmas, for example, simply deletes that row — the remaining dates are
imported untouched.

**Check all** puts everything back. **Uncheck all** empties the list.
The counter at the top always shows how many of the total will be imported.

Click **Import** when the list is right, or **Back** to change countries or years.

### Step 3 — result

A summary shows how many holidays were **created**, how many were **already
present**, and how many schedules were updated.

You will get a summary showing how many holidays were **created**, how many were
**already present**, and how many schedules were updated.

Verify the result under **Time Off → Configuration → Public Holidays**.

---

## Features

**Pick holiday by holiday.** Not every company observes every public holiday.
The second step lists each date individually so you can leave out the ones that do
not apply, instead of importing everything and cleaning up afterwards.

**Several countries at once.** Multinational companies can import Indonesia,
Singapore and Malaysia in a single run. Dates shared between countries — 1 January,
for example — are created only once per schedule.

**Preview before writing.** The wizard lists how many dates were found for each
selected country before anything is created, so you never import blindly.

**Safe to run twice.** Existing dates are detected per schedule and skipped. The
summary reports them as *Already present*. Running the import again after adding a
new working schedule only fills the gap.

**Multiple schedules at once.** Companies with several working schedules (office,
factory, part-time) can update all of them in a single run.

**Reference list you can edit.** Under **Public Holidays → Reference List** you can
browse, search and group the catalogue by country or year, in list or calendar
view. Add your own dates there and they become importable like any other.

**Year range.** Import a single year or several at once, up to 21 years per run.

---

## Bundled countries

Ships with **2025 to 2030** for:

| Asia-Pacific | Europe | Americas | Middle East |
|---|---|---|---|
| Indonesia | Belgium | United States | United Arab Emirates |
| Malaysia | France | Mexico | |
| Singapore | Germany | Brazil | |
| Philippines | Netherlands | | |
| Thailand | Spain | | |
| Vietnam | | | |
| India | | | |

These work immediately, with no additional software.

---

## Unlocking more countries

The module can optionally use the open-source
[`holidays`](https://pypi.org/project/holidays/) Python package, which covers
500+ countries and regions.

Install it on the Odoo server:

```bash
pip install holidays
```

Restart Odoo. In the import wizard, a **Fetch from library** button appears. Pick
any country and year range, click it, and the dates are generated into the
reference list — then import them as usual.

**The module works perfectly well without this package.** It only widens the
country coverage.

> **No data leaves your server.** The `holidays` package computes dates locally
> from built-in rules. This module makes no network calls of any kind.

---

## Indonesia: a note on *cuti bersama*

Only **official national holidays** are included for Indonesia — 17 dates in 2026.

*Cuti bersama* (collective leave) is announced each year by a joint decree of three
ministries, usually a few months in advance. Those dates cannot be computed ahead
of time by anyone, so they are deliberately not included.

Add them manually under **Public Holidays → Reference List → New**, then run the
import. They will then behave exactly like the built-in dates.

---

## How the dates are stored

Imported holidays become standard `resource.calendar.leaves` records — the same
records Odoo itself uses for public holidays. Nothing proprietary is introduced,
so:

* Time Off duration calculations already exclude them.
* They appear in **Time Off → Configuration → Public Holidays**.
* Uninstalling this module does **not** delete them.

Each holiday covers the full local day of its working schedule. Odoo stores
datetimes in UTC, so a holiday on a `Asia/Jakarta` schedule is stored as
`17:00 UTC the previous day` — that is correct and displays as midnight to
Jakarta users.

---

## Security groups

| Group | Can do |
|---|---|
| Internal User | Read the reference list |
| Public Holidays / Administrator | Manage the reference list and run the importer |

Grant the Administrator group under **Settings → Users & Companies → Users**.

---

## Troubleshooting

**A country shows up under “No data yet”**
It is not in the bundled data, or the year range falls outside 2025–2030.
Install the `holidays` package and click **Fetch from library**, which only
generates the countries that are missing.

**“No holiday found for the selected countries between … and …”**
None of the selected countries has data for that year range.
Install the `holidays` package and use **Fetch from library**, or add the dates
manually to the reference list.

**“Two public holidays cannot overlap each other for the same working hours.”**
This is an Odoo core validation. Your database already has a public holiday on
that date with no working schedule assigned (a global holiday). Remove or narrow
the existing entry under **Time Off → Configuration → Public Holidays**.

**“There is no working schedule to add the holidays to.”**
The company has no `resource.calendar`. Create one under
**Settings → Employees → Working Schedules**.

**The Fetch from library button is missing.**
The `holidays` Python package is not installed on the server, or Odoo was not
restarted after installing it.

**Dates look shifted by a few hours.**
Check the timezone of the working schedule
(**Settings → Employees → Working Schedules → Timezone**) and of your user
(**Preferences → Timezone**). Odoo stores UTC and converts for display.

---

## Uninstalling

Uninstalling removes the reference list and the importer, but **keeps** the
holidays you already imported, because those are ordinary Odoo records.

To remove them too, delete them first under
**Time Off → Configuration → Public Holidays**.

---

## Support

Found a bug, or want a country added to the bundled data?
Email **ferhatmuhamad221@gmail.com**.

## License

LGPL-3
