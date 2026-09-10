/** @odoo-module **/

import {
  Component,
  useState,
  useRef,
  onMounted,
  onWillUnmount,
} from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";
import { computeAppsAndMenuItems } from "@web/webclient/menus/menu_helpers";
import { registry } from "@web/core/registry";

export class HomeGrid extends Component {
  setup() {
    this.menuService = useService("menu");
    this.actionService = useService("action");
    this.searchRef = useRef("searchInput");

    // The theme button is only worth showing when something can act on
    // it. fm_dark_mode registers a service of its own name; asking the
    // registry keeps this module free of any dependency on it, and the
    // button simply is not rendered when it is not installed.
    this.hasDarkMode = registry.category("services").contains("fm_dark_mode");
    this.darkMode = this.hasDarkMode ? useService("fm_dark_mode") : null;

    // themeMode: "light" | "dark" | "system"
    // "system" is the default so the interface follows the OS out of the
    // box rather than being stuck on light until someone touches it.
    const savedMode = localStorage.getItem("fm_hg_theme") || "system";
    this.state = useState({
      query: "",
      focusedIndex: -1,
      themeMode: savedMode,
      now: new Date(),
    });

    // This button is no longer the only way to change the theme:
    // fm_dark_mode now puts one in the systray as well. Without listening
    // for the change, pressing that one left this button still showing
    // the old mode - two controls on the same page disagreeing.
    this._syncThemeMode = () => {
      this.state.themeMode =
        (this.darkMode && this.darkMode.mode) ||
        localStorage.getItem("fm_hg_theme") ||
        "system";
    };
    useBus(this.env.bus, "FM_HG:THEME-CHANGED", this._syncThemeMode);

    this._onKeyDown = this._onKeyDown.bind(this);
    this._onStorage = (ev) => {
      // ...and the same user in another tab, which reaches this one only
      // as a storage event.
      if (ev.key === "fm_hg_theme") {
        this._syncThemeMode();
      }
    };
    this._onSystemThemeChange = this._onSystemThemeChange.bind(this);
    this._systemDarkMQ = window.matchMedia("(prefers-color-scheme: dark)");

    onMounted(() => {
      if (this.searchRef.el) {
        this.searchRef.el.focus();
      }
      document.addEventListener("keydown", this._onKeyDown);
      window.addEventListener("storage", this._onStorage);
      this._systemDarkMQ.addEventListener("change", this._onSystemThemeChange);
      // Add class to body for scoping
      document.body.classList.add("o_fm_hg-active");
      this._clock = setInterval(() => {
        this.state.now = new Date();
      }, 1000);
    });

    onWillUnmount(() => {
      clearInterval(this._clock);
      document.removeEventListener("keydown", this._onKeyDown);
      window.removeEventListener("storage", this._onStorage);
      this._systemDarkMQ.removeEventListener(
        "change",
        this._onSystemThemeChange,
      );
      document.body.classList.remove("o_fm_hg-active");
    });
  }

  // ── Data ──────────────────────────────────────────────

  get apps() {
    const tree = this.menuService.getMenuAsTree("root");
    const { apps } = computeAppsAndMenuItems(tree);
    return apps;
  }

  get filteredApps() {
    const q = this.state.query.toLowerCase().trim();
    if (!q) return this.apps;
    return this.apps.filter((a) => a.label.toLowerCase().includes(q));
  }

  get searchResults() {
    const q = this.state.query.toLowerCase().trim();
    if (!q) return [];
    const tree = this.menuService.getMenuAsTree("root");
    const { menuItems } = computeAppsAndMenuItems(tree);
    return menuItems
      .filter(
        (m) =>
          m.label.toLowerCase().includes(q) ||
          (m.parents && m.parents.toLowerCase().includes(q)),
      )
      .slice(0, 12);
  }

  get allItems() {
    return this.state.query
      ? [...this.filteredApps, ...this.searchResults]
      : this.filteredApps;
  }

  // ── Icon helpers ─────────────────────────────────────

  getAppIcon(app) {
    if (app.webIconData) {
      const src = app.webIconData;
      // Enterprise default icon fallback
      if (src.startsWith("/web_enterprise/")) {
        return {
          type: "icon",
          iconClass: "fa fa-cube",
          color: "#FFFFFF",
          backgroundColor: "#714B67",
        };
      }
      if (src.startsWith("data:image")) {
        return { type: "img", src };
      }
      if (src.startsWith("/")) {
        return { type: "img", src };
      }
      // raw base64
      const prefix =
        src.charAt(0) === "P"
          ? "data:image/svg+xml;base64,"
          : "data:image/png;base64,";
      return { type: "img", src: prefix + src.replace(/\s/g, "") };
    }
    if (app.webIcon) {
      return {
        type: "icon",
        iconClass: app.webIcon.iconClass || "fa fa-cube",
        color: app.webIcon.color || "#FFFFFF",
        backgroundColor: app.webIcon.backgroundColor || "#714B67",
      };
    }
    return {
      type: "icon",
      iconClass: "fa fa-cube",
      color: "#FFFFFF",
      backgroundColor: "#714B67",
    };
  }

  // ── Search ───────────────────────────────────────────

  onSearchInput(ev) {
    this.state.query = ev.target.value;
    this.state.focusedIndex = -1;
  }

  clearSearch() {
    this.state.query = "";
    this.state.focusedIndex = -1;
    if (this.searchRef.el) {
      this.searchRef.el.focus();
    }
  }

  // ── Theme Mode ───────────────────────────────────────

  /**
   * Returns true when the grid should render in dark style.
   * "dark" → always dark, "system" → follow OS, "light" → always light.
   */
  // ── Banner ───────────────────────────────────────────────────

  /**
   * Display name of the signed-in user, without the company prefix.
   *
   * Odoo 17 registers a `user` service. Odoo 18 and 19 replaced it with a
   * plain module and, on the way, delete `session.name` right after reading
   * it - so that field is empty by the time a component renders.
   * `partner_display_name` survives everywhere, but reads "Company, Person"
   * when the user belongs to a company.
   */
  get userName() {
    const service = this.env.services.user;
    if (service && service.name) {
      return service.name;
    }
    const display = session.partner_display_name || "";
    const separator = display.indexOf(", ");
    return separator > -1 ? display.slice(separator + 2) : display;
  }

  /** Four buckets, so languages that split the afternoon still read right. */
  get greeting() {
    const hour = this.state.now.getHours();
    if (hour < 11) return _t("Good morning");
    if (hour < 15) return _t("Good day");
    if (hour < 18) return _t("Good afternoon");
    return _t("Good evening");
  }

  get clock() {
    return this.state.now.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  get dateLabel() {
    return this.state.now.toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  get isDark() {
    if (this.state.themeMode === "dark") return true;
    if (this.state.themeMode === "system") {
      return this._systemDarkMQ && this._systemDarkMQ.matches;
    }
    return false;
  }


  /** Cycle light -> dark -> system. Only reachable when fm_dark_mode
   *  is installed, since the button is not rendered otherwise. */
  cycleTheme() {
    if (!this.darkMode) {
      return;
    }
    this.state.themeMode = this.darkMode.cycle();
  }

  /** Icon for the CURRENT mode, so the button says what is in force
   *  rather than what pressing it would do. */
  get themeIcon() {
    if (this.state.themeMode === "dark") return "fa-moon-o";
    if (this.state.themeMode === "light") return "fa-sun-o";
    return "fa-adjust";
  }

  get themeTitle() {
    if (this.state.themeMode === "dark") return _t("Theme: Dark");
    if (this.state.themeMode === "light") return _t("Theme: Light");
    return _t("Theme: follows your system");
  }

  /** React to OS theme change while in system mode */
  _onSystemThemeChange() {
    // Force a reactive re-render when in system mode
    if (this.state.themeMode === "system") {
      this.state.themeMode = "system"; // triggers OWL reactivity
      // Also update global dark class
      this.env.bus.trigger("FM_HG:THEME-CHANGED");
    }
  }



  // ── Keyboard ─────────────────────────────────────────

  _onKeyDown(ev) {
    const items = this.allItems;
    const len = items.length;
    if (!len) return;

    switch (ev.key) {
      case "ArrowRight":
      case "ArrowDown":
        ev.preventDefault();
        this.state.focusedIndex = (this.state.focusedIndex + 1) % len;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        ev.preventDefault();
        this.state.focusedIndex = (this.state.focusedIndex - 1 + len) % len;
        break;
      case "Enter":
        if (this.state.focusedIndex >= 0) {
          ev.preventDefault();
          this.openMenu(items[this.state.focusedIndex]);
        }
        break;
      case "Escape":
        if (this.state.query) {
          ev.preventDefault();
          this.clearSearch();
        }
        break;
    }
  }

  // ── Navigation ───────────────────────────────────────

  openMenu(item) {
    // Explicitly hide the homegrid first — this is needed when re-entering
    // the same module, because Odoo won't fire MENUS:APP-CHANGED in that case.
    this.env.bus.trigger("FM_HG:HIDE-HOME");
    this.menuService.selectMenu(item);
  }
}

HomeGrid.template = "fm_home_grid.HomeGrid";
HomeGrid.props = {};
