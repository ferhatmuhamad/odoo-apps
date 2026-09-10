/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

/**
 * Dark mode, as a service.
 *
 * The theme is a single string in localStorage under `fm_hg_theme`:
 * "light" | "dark" | "system". Everything else — the body class, the
 * toggle button, other modules — derives from it, so there is exactly
 * one place where the truth lives.
 *
 * Registering this as a SERVICE is also how other modules find out
 * dark mode is installed at all: `registry.category("services")
 * .contains("fm_dark_mode")`. That lets fm_home_grid show its theme
 * button only when there is something to toggle, without either
 * module having to depend on the other.
 */

const KEY = "fm_hg_theme";
const CLASS = "fm-dark";
const BUS_EVENT = "FM_HG:THEME-CHANGED";
const MODES = ["light", "dark", "system"];

export const darkModeService = {
  dependencies: ["ui"],

  start(env) {
    const mq = browser.matchMedia("(prefers-color-scheme: dark)");

    const read = () => {
      const stored = browser.localStorage.getItem(KEY);
      return MODES.includes(stored) ? stored : "system";
    };

    const isDark = () => {
      const mode = read();
      return mode === "dark" || (mode === "system" && mq.matches);
    };

    const apply = () => {
      document.body.classList.toggle(CLASS, isDark());
    };

    // Applied straight away rather than on mount. The class belongs to
    // <body>, which outlives every component, so waiting for a mount
    // only means a visible flash of the wrong theme first.
    apply();

    // ...and then defended, because applying it once is not enough.
    //
    // While booting, Odoo ASSIGNS document.body.className outright
    // rather than adding to it - the body ends up as exactly
    // "o_web_client" and our class is gone with no error anywhere. The
    // symptom is oddly specific: the theme works when you press the
    // toggle, and is missing again after a reload. Watching the
    // attribute puts it back whenever that happens, whoever did it.
    new MutationObserver(() => {
      if (document.body.classList.contains(CLASS) !== isDark()) {
        apply();
      }
    }).observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
    });

    mq.addEventListener("change", apply);

    // Another tab changed the theme.
    browser.addEventListener("storage", (ev) => {
      if (ev.key === KEY) {
        apply();
      }
    });

    // THE "I HAD TO RELOAD" BUG.
    //
    // Leave Odoo open in a background tab through the afternoon and the
    // OS flips to dark in the evening: browsers throttle background
    // tabs and the matchMedia "change" event can simply never be
    // delivered. The page then sits in the old theme until it is
    // reloaded, which is exactly what was reported. Re-checking
    // whenever the tab becomes visible again costs one class toggle
    // and closes that hole.
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        apply();
      }
    });

    // Theme changed from somewhere inside this tab.
    env.bus.addEventListener(BUS_EVENT, apply);

    return {
      /** Re-assert the body class. Exposed because the web client has to
       *  call it again after it mounts: Odoo rewrites `document.body`'s
       *  class list while booting, which silently drops ours. Applying
       *  once at service start is not enough - that was the whole reason
       *  the original module hooked into the web client instead. */
      apply,
      get mode() {
        return read();
      },
      get isDark() {
        return isDark();
      },
      /** Move to the next mode: light -> dark -> system -> light. */
      cycle() {
        const next = MODES[(MODES.indexOf(read()) + 1) % MODES.length];
        this.set(next);
        return next;
      },
      set(mode) {
        if (!MODES.includes(mode)) {
          return;
        }
        browser.localStorage.setItem(KEY, mode);
        apply();
        // Tell anything else on the page (the home grid, for one) that
        // the theme moved, so it can re-render its own indicator.
        env.bus.trigger(BUS_EVENT);
      },
    };
  },
};

registry.category("services").add("fm_dark_mode", darkModeService);
