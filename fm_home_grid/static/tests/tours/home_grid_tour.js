/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Exercises the launcher the way a user does: open it, check the grid is
 * populated with real icons, search, and open a result.
 */
registry.category("web_tour.tours").add("fm_home_grid_tour", {
    url: "/odoo",
    steps: () => [
        {
            content: "Open the home grid from the navbar",
            trigger: ".o_main_navbar .o_fm_hg-navbar-btn",
            run: "click",
        },
        {
            content: "The home screen is showing",
            trigger: ".o_fm_hg .o_fm_hg-search-input",
        },
        {
            content: "The banner greets the signed-in user",
            trigger: ".o_fm_hg .o_fm_hg-username",
        },
        {
            content: "The grid lists at least one app",
            trigger: ".o_fm_hg .o_fm_hg-grid .o_fm_hg-app",
        },
        {
            content: "App icons are real images, not broken base64",
            trigger: ".o_fm_hg .o_fm_hg-app-icon[src^='data:image']",
        },
        {
            content: "Search for Settings",
            trigger: ".o_fm_hg .o_fm_hg-search-input",
            run: "edit Settings",
        },
        {
            content: "A matching app is shown",
            trigger: ".o_fm_hg .o_fm_hg-app",
            run: "click",
        },
        {
            content: "The web client is back with the navbar in place",
            trigger: ".o_main_navbar .o_menu_systray",
        },
    ],
});
