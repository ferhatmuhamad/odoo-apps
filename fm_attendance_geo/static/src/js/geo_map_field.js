/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { createMap, fenceBounds, fenceLayers, formatDistance, personMarker } from "./leaflet_map";

/**
 * One map widget, two jobs.
 *
 * mode "fence"  - on a work location. Shows the pin and the radius circle;
 *                 clicking or dragging moves the pin, and the circle follows
 *                 the radius field as it is typed.
 * mode "point"  - on an attendance. Shows where the person was, the fence
 *                 the verdict was reached against (the snapshot stored with
 *                 it, not today's pin), and the distance between them.
 */
export class GeoMapField extends Component {
  static template = "fm_attendance_geo.GeoMapField";
  static props = {
    ...standardFieldProps,
    mode: { type: String, optional: true },
    side: { type: String, optional: true },
  };
  static defaultProps = { mode: "point", side: "in" };

  setup() {
    this.orm = useService("orm");
    this.mapRef = useRef("map");
    this.map = null;
    this.layers = [];
    this.fitted = null; // the point the view was last fitted to
    this.state = useState({ ready: false, failed: false });

    onMounted(() => this.mount());
    onWillUnmount(() => this.unmount());
    // Redraw whenever the numbers the map is drawn from change.
    useEffect(
      () => {
        if (this.map) {
          this.draw();
        }
      },
      () => [this.map, ...this.watched()]
    );
  }

  // ── What the map is drawn from ──────────────────────────────────────

  get data() {
    return this.props.record.data;
  }

  get isFence() {
    return this.props.mode === "fence";
  }

  get point() {
    if (this.isFence) {
      const f = this.data[this.props.name] || {};
      return f.has_point ? { lat: f.lat, lng: f.lng } : null;
    }
    const lat = this.data[`${this.props.side}_latitude`];
    const lng = this.data[`${this.props.side}_longitude`];
    return lat && lng ? { lat, lng } : null;
  }

  get fence() {
    if (this.isFence) {
      const f = this.data[this.props.name] || {};
      return f.has_point ? f : null;
    }
    const f = this.data[this.props.name];
    return f && f.lat && f.lng ? f : null;
  }

  get status() {
    return this.isFence ? null : this.data[`${this.props.side}_fm_geo_status`];
  }

  get distance() {
    return this.isFence ? null : this.data[`${this.props.side}_fm_geo_distance`];
  }

  get hasContent() {
    return !!(this.point || this.fence || this.isFence);
  }

  get emptyText() {
    return _t("No position was recorded for this check.");
  }

  watched() {
    const f = this.fence || {};
    const p = this.point || {};
    return [p.lat, p.lng, f.lat, f.lng, f.radius, this.status, this.distance, this.props.readonly];
  }

  // ── Leaflet ────────────────────────────────────────────────────────

  async mount() {
    if (!this.hasContent || !this.mapRef.el) {
      return;
    }
    try {
      this.map = await createMap(this.mapRef.el, this.orm, {
        scrollWheelZoom: this.isFence,
      });
    } catch (e) {
      this.state.failed = true;
      return;
    }
    if (this.isFence) {
      this.map.on("click", (ev) => this.place(ev.latlng));
    }
    this.state.ready = true;
    this.draw();
    // The container may have been laid out after Leaflet measured it.
    requestAnimationFrame(() => this.map && this.map.invalidateSize());
  }

  unmount() {
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
  }

  clear() {
    for (const layer of this.layers) {
      layer.remove();
    }
    this.layers = [];
  }

  draw() {
    const L = window.L;
    this.clear();
    const bounds = [];

    const fence = this.fence;
    if (fence) {
      const draggable = this.isFence && !this.props.readonly;
      const { circle, pin } = fenceLayers(fence, this.status, { draggable });
      circle.addTo(this.map);
      pin.addTo(this.map);
      this.layers.push(circle, pin);
      bounds.push(fenceBounds(fence));
      if (draggable) {
        pin.on("dragend", (ev) => this.place(ev.target.getLatLng()));
      }
      pin.bindTooltip(fence.name || "", { direction: "top", offset: [0, -8] });
    }

    const point = this.point;
    if (point && !this.isFence) {
      const marker = personMarker(point.lat, point.lng, this.status);
      marker.addTo(this.map);
      this.layers.push(marker);
      marker.bindPopup(this.popupHtml(), { className: "fm_geo_popup", autoPan: false });
      bounds.push(L.latLng(point.lat, point.lng));
    }

    // Fit the view to what is drawn - but on the location form only when
    // the pin moved, not on every keystroke in the radius field. Typing
    // "350" and watching the map zoom out three times is not a preview.
    const anchor = fence ? `${fence.lat},${fence.lng}` : point ? `${point.lat},${point.lng}` : "";
    const refit = !this.isFence || this.fitted !== anchor;
    if (bounds.length && refit) {
      const all = L.latLngBounds([]);
      for (const b of bounds) {
        all.extend(b);
      }
      // Room at the top for the popup, which sits above its marker and was
      // otherwise cut off when the person was the northernmost thing shown.
      this.map.fitBounds(all, { paddingTopLeft: [28, 96], paddingBottomRight: [28, 28], maxZoom: 17 });
      this.fitted = anchor;
    } else if (!bounds.length) {
      this.map.setView([0, 0], 2);
    }
    for (const layer of this.layers) {
      if (layer.getPopup && layer.getPopup()) {
        layer.openPopup();
      }
    }
  }

  popupHtml() {
    const label = this.props.side === "out" ? _t("Check-out") : _t("Check-in");
    const status = {
      in: _t("In area"),
      out: _t("Out of area"),
      unknown: _t("No position"),
      exempt: _t("Exempt"),
    }[this.status] || "";
    const parts = [`<b>${label}</b>`];
    if (status) {
      parts.push(status);
    }
    if (this.fence && this.distance !== null && this.distance !== false) {
      parts.push(_t("%(distance)s from %(name)s", {
        distance: formatDistance(this.distance),
        name: escape(this.fence.name || ""),
      }));
    }
    return parts.join("<br/>");
  }

  place(latlng) {
    if (this.props.readonly) {
      return;
    }
    this.props.record.update({
      fm_geo_latitude: Number(latlng.lat.toFixed(7)),
      fm_geo_longitude: Number(latlng.lng.toFixed(7)),
    });
  }
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export const geoMapField = {
  component: GeoMapField,
  supportedTypes: ["json"],
  extractProps: ({ options }) => ({
    mode: options.mode,
    side: options.side,
  }),
};

registry.category("fields").add("fm_geo_map", geoMapField);
