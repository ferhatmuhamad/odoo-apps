/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { createMap, fenceBounds, fenceLayers, formatDistance, personMarker, statusColor } from "./leaflet_map";

/**
 * Every check-in of one day and every office, on one map.
 *
 * For the HR officer who wants to see, at a glance, who is where. The list
 * beside the map is the same people sorted with the problems first; clicking
 * a row flies to the person, clicking a person opens their attendance.
 */
export class DayMapAction extends Component {
  static template = "fm_attendance_geo.DayMapAction";
  static props = { "*": true };

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.mapRef = useRef("map");
    this.map = null;
    this.layers = [];
    this.markers = {};
    this.state = useState({
      day: today(),
      loading: true,
      failed: false,
      fences: [],
      points: [],
      summary: null,
    });

    onMounted(async () => {
      try {
        this.map = await createMap(this.mapRef.el, this.orm, { scrollWheelZoom: true });
      } catch (e) {
        this.state.failed = true;
        return;
      }
      await this.load();
    });
    onWillUnmount(() => this.map && this.map.remove());
  }

  // ── Data ────────────────────────────────────────────────────────────

  async load() {
    this.state.loading = true;
    const data = await this.orm.call("hr.attendance", "fm_geo_map_data", [this.state.day]);
    this.state.fences = data.fences;
    this.state.points = data.points;
    this.state.summary = data.summary;
    this.state.loading = false;
    this.draw();
  }

  onDayChange(ev) {
    if (ev.target.value) {
      this.state.day = ev.target.value;
      this.load();
    }
  }

  shiftDay(delta) {
    const d = new Date(this.state.day + "T12:00:00");
    d.setDate(d.getDate() + delta);
    this.state.day = d.toISOString().slice(0, 10);
    this.load();
  }

  /** Problems first, then everyone else in check-in order. */
  get rows() {
    const rank = { out: 0, unknown: 1, exempt: 3, in: 3, none: 4 };
    return [...this.state.points].sort((a, b) => {
      const ra = a.flagged ? -1 : rank[a.status] ?? 4;
      const rb = b.flagged ? -1 : rank[b.status] ?? 4;
      return ra - rb || a.check_in.localeCompare(b.check_in);
    });
  }

  statusLabel(status) {
    return {
      in: _t("In area"),
      out: _t("Out of area"),
      unknown: _t("No position"),
      exempt: _t("Exempt"),
      none: _t("No geofence"),
    }[status] || "";
  }

  statusColor(status) {
    return statusColor(status);
  }

  formatDistance(m) {
    return formatDistance(m);
  }

  // ── Map ─────────────────────────────────────────────────────────────

  draw() {
    const L = window.L;
    for (const layer of this.layers) {
      layer.remove();
    }
    this.layers = [];
    this.markers = {};
    const bounds = L.latLngBounds([]);

    for (const fence of this.state.fences) {
      const { circle, pin } = fenceLayers(fence, null);
      circle.addTo(this.map);
      pin.addTo(this.map);
      pin.bindTooltip(`${fence.name} · ${fence.radius} m`, { direction: "top", offset: [0, -8] });
      this.layers.push(circle, pin);
      bounds.extend(fenceBounds(fence));
    }

    for (const p of this.state.points) {
      const marker = personMarker(p.lat, p.lng, p.status);
      marker.addTo(this.map);
      marker.bindPopup(this.popupHtml(p), { className: "fm_geo_popup" });
      marker.on("popupopen", () => {
        const link = marker.getPopup().getElement().querySelector("[data-open]");
        if (link) {
          link.addEventListener("click", (ev) => {
            ev.preventDefault();
            this.open(p.id);
          });
        }
      });
      this.layers.push(marker);
      this.markers[p.id] = marker;
      bounds.extend([p.lat, p.lng]);
    }

    if (bounds.isValid()) {
      this.map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
    } else {
      this.map.setView([0, 0], 2);
    }
  }

  popupHtml(p) {
    const lines = [`<b>${esc(p.employee)}</b> · ${esc(p.check_in)}`];
    let status = this.statusLabel(p.status);
    if (p.location && p.distance !== null && p.distance !== false) {
      status += ` · ${formatDistance(p.distance)} ${_t("from")} ${esc(p.location)}`;
    }
    lines.push(status);
    if (p.reason) {
      lines.push(`<i>${esc(p.reason)}</i>`);
    }
    if (p.flagged) {
      lines.push(`<span style="color:${statusColor("out")}">${_t("GPS flagged")}</span> ${esc(p.note)}`);
    }
    lines.push(`<a href="#" data-open="1">${_t("Open attendance")}</a>`);
    return lines.join("<br/>");
  }

  focus(p) {
    const marker = this.markers[p.id];
    if (marker) {
      this.map.flyTo([p.lat, p.lng], Math.max(this.map.getZoom(), 16), { duration: 0.6 });
      marker.openPopup();
    }
  }

  open(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "hr.attendance",
      res_id: id,
      views: [[false, "form"]],
      target: "current",
    });
  }
}

function today() {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

registry.category("actions").add("fm_attendance_geo.day_map", DayMapAction);
