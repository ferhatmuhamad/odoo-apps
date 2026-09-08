/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { useState, onMounted, onWillUnmount } from "@odoo/owl";

patch(NavBar.prototype, {
  setup() {
    super.setup(...arguments);

    // Reactive state: homeGridVisible controls grid vs app icon.
    // _appTick forces a re-render when MENUS:APP-CHANGED fires,
    // because selectMenu() is async and currentApp is only updated
    // inside onActionReady — after OWL already re-rendered for HIDE-HOME.
    this.fmState = useState({ homeGridVisible: false, _appTick: 0 });

    const onToggleHome = () => {
      this.fmState.homeGridVisible = true;
    };
    const onHideHome = () => {
      this.fmState.homeGridVisible = false;
    };
    const onAppChanged = () => {
      this.fmState.homeGridVisible = false;
      // Increment tick to force re-render now that currentApp is set
      this.fmState._appTick++;
    };

    this.env.bus.addEventListener("FM_HG:TOGGLE-HOME", onToggleHome);
    this.env.bus.addEventListener("FM_HG:HIDE-HOME", onHideHome);
    this.env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);

    onMounted(() => {
      this.fmState.homeGridVisible =
        sessionStorage.getItem("fm_hg_visible") === "1";
    });

    onWillUnmount(() => {
      this.env.bus.removeEventListener("FM_HG:TOGGLE-HOME", onToggleHome);
      this.env.bus.removeEventListener("FM_HG:HIDE-HOME", onHideHome);
      this.env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
    });
  },

  /**
   * Returns a data-URL for the current app's icon,
   * or "" when on homegrid / no app → template shows grid icon.
   */
  get fmAppIconSrc() {
    // Touch reactive deps so OWL knows to re-render
    void this.fmState._appTick;
    if (this.fmState.homeGridVisible) return "";
    const app = this.currentApp;
    if (!app || !app.webIconData) return "";
    const raw = app.webIconData;
    if (raw.startsWith("data:image")) return raw;
    if (raw.startsWith("/")) return raw;
    const prefix = raw.startsWith("P")
      ? "data:image/svg+xml;base64,"
      : "data:image/png;base64,";
    return prefix + raw.replace(/\s/g, "");
  },
});
