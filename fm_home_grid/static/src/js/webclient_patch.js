/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { HomeGrid } from "./home_grid";
import { patch } from "@web/core/utils/patch";
import { useState, onMounted, onWillUnmount } from "@odoo/owl";

/**
 * Check whether the current URL hash contains an action or menu,
 * meaning the user is already inside a module view.
 */
function _hasActionInHash() {
  const hash = window.location.hash || "";
  return hash.includes("action=") || hash.includes("menu_id=");
}

patch(WebClient.prototype, {
  setup() {
    super.setup(...arguments);

    // The navbar's dark rules hang off `body.fm-dark`. That class used to come
    // from a separate theme module, so without this the dark styles never
    // applied. Track the OS preference here, on the WebClient, so the whole
    // interface follows it - not just the home screen.
    this._fmDarkMQ = window.matchMedia("(prefers-color-scheme: dark)");
    this._fmSyncDark = () => {
      const mode = localStorage.getItem("fm_hg_theme") || "system";
      const dark = mode === "dark" || (mode === "system" && this._fmDarkMQ.matches);
      document.body.classList.toggle("fm-dark", dark);
    };
    this._fmSyncDark();
    this._fmDarkMQ.addEventListener("change", this._fmSyncDark);
    this.env.bus.addEventListener("FM_HG:THEME-CHANGED", this._fmSyncDark);

    // Determine initial view: if user was on homegrid before refresh, stay there.
    const wasOnGrid = sessionStorage.getItem("fm_hg_visible") === "1";
    const startOnGrid = wasOnGrid || !_hasActionInHash();
    this.fmHgState = useState({ showHomeGrid: startOnGrid });
    // Persist initial state
    sessionStorage.setItem("fm_hg_visible", startOnGrid ? "1" : "0");

    // When restoring homegrid after refresh, Odoo will still auto-load the
    // last action from the URL hash, firing APP-CHANGED. We skip that first
    // event so the homegrid stays visible.
    this._fmSkipAppChanged = startOnGrid && _hasActionInHash();

    // Helper: hide the homegrid and show the action manager
    const hideHomeGrid = () => {
      if (!this.fmHgState.showHomeGrid) return;
      this.fmHgState.showHomeGrid = false;
      sessionStorage.setItem("fm_hg_visible", "0");
      this._fmHgToggleAM(true);
    };

    // Skip flags for the first events after a refresh (to keep homegrid visible)
    this._fmSkipUiUpdated = startOnGrid && _hasActionInHash();

    const onAppChanged = () => {
      if (this._fmSkipAppChanged) {
        this._fmSkipAppChanged = false;
        this._fmHgToggleAM(false);
        return;
      }
      if (this.menuService.getCurrentApp()) {
        hideHomeGrid();
      }
    };

    // Fired when action_manager renders a new action (catches activity clicks,
    // breadcrumb nav, URL changes, etc.)
    const onActionUiUpdated = () => {
      if (this._fmSkipUiUpdated) {
        this._fmSkipUiUpdated = false;
        return;
      }
      hideHomeGrid();
    };

    // Fired from homegrid openMenu – handles re-entering the same module
    const onHideHome = () => {
      hideHomeGrid();
    };

    const onToggleHome = () => {
      this.fmHgState.showHomeGrid = true;
      sessionStorage.setItem("fm_hg_visible", "1");
      this._fmHgToggleAM(false);
    };

    this.env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);
    this.env.bus.addEventListener(
      "ACTION_MANAGER:UI-UPDATED",
      onActionUiUpdated,
    );
    this.env.bus.addEventListener("FM_HG:HIDE-HOME", onHideHome);
    this.env.bus.addEventListener("FM_HG:TOGGLE-HOME", onToggleHome);

    onMounted(() => {
      this._fmHgToggleAM(!this.fmHgState.showHomeGrid);
    });

    onWillUnmount(() => {
      this._fmDarkMQ.removeEventListener("change", this._fmSyncDark);
      this.env.bus.removeEventListener("FM_HG:THEME-CHANGED", this._fmSyncDark);
      this.env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
      this.env.bus.removeEventListener(
        "ACTION_MANAGER:UI-UPDATED",
        onActionUiUpdated,
      );
      this.env.bus.removeEventListener("FM_HG:HIDE-HOME", onHideHome);
      this.env.bus.removeEventListener("FM_HG:TOGGLE-HOME", onToggleHome);
    });
  },

  _fmHgToggleAM(show) {
    const el = document.querySelector(".o_action_manager");
    if (el) {
      el.style.display = show ? "" : "none";
    }
  },

  async _loadDefaultApp() {
    this.fmHgState.showHomeGrid = true;
    sessionStorage.setItem("fm_hg_visible", "1");
    this._fmHgToggleAM(false);
  },
});

// Register component on WebClient
WebClient.components = {
  ...WebClient.components,
  HomeGrid,
};
