/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

const KEY = "fm_hg_theme";

/**
 * The theme switch, in the systray.
 *
 * Without it this module has no control surface of its own. Installed
 * alone it still works - the theme follows the operating system - but
 * there was no way to override that, because the only button was the one
 * fm_home_grid draws beside its search box. A module that stands on its
 * own perfectly well therefore looked like it needed another one.
 *
 * Deliberately a plain button and not a Dropdown: Odoo's Dropdown
 * component changed API between 17.0 and 18.0, while one button that
 * cycles is the same code on all three series.
 */
export class ThemeSwitch extends Component {
  static template = "fm_dark_mode.ThemeSwitch";
  static props = {};

  setup() {
    this.darkMode = useService("fm_dark_mode");

    // The mode itself lives in localStorage; this is only a copy so that
    // OWL knows when to redraw. Three different things can move it: this
    // button, the home grid's button, and the same user in another tab.
    this.state = useState({ mode: this.darkMode.mode });
    const sync = () => {
      this.state.mode = this.darkMode.mode;
    };

    useBus(this.env.bus, "FM_HG:THEME-CHANGED", sync);

    // Another tab. The service already re-applies the body class on this
    // event, but keeping the button's own label honest is ours to do.
    const onStorage = (ev) => {
      if (ev.key === KEY) {
        sync();
      }
    };
    onMounted(() => browser.addEventListener("storage", onStorage));
    onWillUnmount(() => browser.removeEventListener("storage", onStorage));
  }

  /** Icon for the mode IN FORCE, not for what a click would do. */
  get icon() {
    if (this.state.mode === "dark") {
      return "fa-moon-o";
    }
    if (this.state.mode === "light") {
      return "fa-sun-o";
    }
    return "fa-adjust";
  }

  /**
   * Names the mode in force AND what pressing the button does. A single
   * icon that silently rotates through three states is a guessing game;
   * saying where the next press lands is what makes the third state -
   * "follow the system" - findable at all.
   */
  get title() {
    if (this.state.mode === "dark") {
      return _t("Theme: Dark — click to follow your system");
    }
    if (this.state.mode === "light") {
      return _t("Theme: Light — click for Dark");
    }
    return _t("Theme: follows your system — click for Light");
  }

  onClick() {
    this.state.mode = this.darkMode.cycle();
  }
}

// Sits to the left of the user menu, which registers itself last.
registry
  .category("systray")
  .add("fm_dark_mode.ThemeSwitch", { Component: ThemeSwitch }, { sequence: 25 });
