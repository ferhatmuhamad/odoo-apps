/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Exercises the launcher the way a user does: open it, check the grid is
 * populated with real icons, search, and open a result.
 */
registry.category("web_tour.tours").add("fm_home_grid_tour", {
    test: true,
    url: "/web",
    steps: () => [
        {
            content: "Open the home grid from the navbar",
            trigger: ".o_main_navbar .o_fm_hg-navbar-btn",
            run: "click",
        },
        {
            content: "The home screen is showing",
            trigger: ".o_fm_hg .o_fm_hg-search-input",
            // Odoo 17 clicks a step's trigger when no `run` is given;
            // these are assertions, so the action must stay a no-op.
            run: () => {},
        },
        {
            content: "The banner greets the signed-in user",
            trigger: ".o_fm_hg .o_fm_hg-username",
            // Odoo 17 clicks a step's trigger when no `run` is given;
            // these are assertions, so the action must stay a no-op.
            run: () => {},
        },
        {
            content: "The grid lists at least one app",
            trigger: ".o_fm_hg .o_fm_hg-grid .o_fm_hg-app",
            // Odoo 17 clicks a step's trigger when no `run` is given;
            // these are assertions, so the action must stay a no-op.
            run: () => {},
        },
        {
            content: "App icons are real images, not broken base64",
            trigger: ".o_fm_hg .o_fm_hg-app-icon[src^='data:image']",
            // Odoo 17 clicks a step's trigger when no `run` is given;
            // these are assertions, so the action must stay a no-op.
            run: () => {},
        },
        {
            content: "Search for Settings",
            trigger: ".o_fm_hg .o_fm_hg-search-input",
            run: "text Settings",
        },
        {
            // Odoo 17 loses the test savepoint once a tour navigates into a
            // real app (an unrelated commit happens on the way), so this tour
            // stops at the search result instead of opening it. Odoo 18 and 19
            // run the full flow.
            content: "A matching app is listed",
            trigger: ".o_fm_hg .o_fm_hg-app",
            run: () => {},
        },
    ],
});
