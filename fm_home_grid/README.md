# Modern Home Grid

A full-page app launcher for Odoo Community, with instant search.

Odoo Community lists your apps in a narrow dropdown. This module replaces it
with a full-page grid: every app as a large icon, on a designed background, with
a search box that filters apps **and their menu items** as you type.

---

## Table of contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [How to use it](#how-to-use-it)
4. [Keyboard shortcuts](#keyboard-shortcuts)
5. [What it changes](#what-it-changes)
6. [Design notes](#design-notes)
7. [Troubleshooting](#troubleshooting)
8. [Uninstalling](#uninstalling)
9. [Licence and support](#licence-and-support)

---

## Requirements

| | |
|---|---|
| Odoo | 17.0, 18.0 or 19.0 — Community or Enterprise |
| Depends on | `web` only — part of every Odoo installation |
| Extra Python packages | None |
| Server configuration | None |

There is no data model, no scheduled action and no server-side processing. The
module is pure interface.

---

## Installation

1. Copy the `fm_home_grid` folder into your Odoo `addons_path`.
2. Restart the Odoo service.
3. Go to **Apps**, click **Update Apps List**.
4. Remove the *Apps* filter, search for **Modern Home Grid**, click **Install**.

Refresh your browser once after installing so the new interface assets load.

---

## How to use it

Click the **grid icon** at the far left of the top bar — the same place the app
menu has always been.

The launcher opens full screen:

* **Browse** — every app you have access to, as a large icon.
* **Search** — start typing. Results cover both apps and the menu items inside
  them, so typing `invoice` finds *Invoicing* as well as *Customer Invoices*.
* **Open** — click a tile, or press Enter on the highlighted one.
* **Close** — press Escape, or use the × in the top right corner.

Nothing to configure. Users see exactly the apps their access rights allow,
because the launcher reads the same menu data as the standard Odoo interface.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| Type anything | Filter apps and menus |
| `←` `→` `↑` `↓` | Move between tiles |
| `Enter` | Open the highlighted tile |
| `Escape` | Close the launcher |

The search box is focused the moment the launcher opens, so you can start typing
straight away.

---

## What it changes

**Added:** one button in the top bar, and the full-page launcher it opens.

**Hidden:** the standard apps dropdown — hidden with CSS only. The original
element stays in the page untouched, so nothing else in Odoo is affected.

**Not touched:** no models, no views, no access rights, no records. Uninstalling
returns Odoo to exactly its previous state.

---

## Design notes

* The search box is deliberately narrower than the grid, so the eye lands on it
  first instead of reading one long straight edge.
* The background is a soft gradient with blurred colour fields and a faint grid
  texture — quiet enough to sit behind icons all day.
* Tiles lift slightly on hover, and the icon grows a little. No animation runs
  on its own, and everything stops if the operating system requests reduced
  motion.
* Light and dark themes are both handled, following the viewer's system setting.

---

## Troubleshooting

**The button does not appear after installing.**
Browser assets are cached. Force a reload with `Ctrl+Shift+R`
(`Cmd+Shift+R` on macOS), or clear the browser cache.

**The old dropdown appears instead of the launcher.**
Another module is also customising the top bar. Try disabling other backend
themes; two modules changing the same area will conflict.

**Some apps are missing from the grid.**
The launcher shows only what your user may open. Check the user's access rights
under **Settings → Users & Companies → Users**.

**Search finds an app but not its menus.**
Menu items appear only for apps you can access, and only down to two levels.
Deeply nested menus are intentionally left out to keep results readable.

---

## Uninstalling

Uninstall from **Apps**. The standard Odoo apps dropdown returns immediately.
No data of any kind is left behind, because the module never created any.

---

## Licence and support

Licensed under **LGPL-3**. You are free to use, modify and redistribute it.

Questions or a bug to report: **ferhatmuhamad221@gmail.com**
