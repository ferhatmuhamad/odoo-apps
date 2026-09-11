/** @odoo-module **/

/**
 * The little of Leaflet this module needs, in one place.
 *
 * Leaflet is vendored (static/lib/leaflet) and registers itself on window.L
 * when the bundle loads. Every map here is built through `createMap`, so the
 * tile server and its attribution - both settings - are fetched once and
 * applied everywhere.
 */

const STATUS_COLOR = {
  in: "#1f9d55",
  out: "#d23b3b",
  unknown: "#c08a1a",
  exempt: "#6c757d",
  none: "#6c757d",
};

let configPromise = null;

export function mapConfig(orm) {
  if (!configPromise) {
    configPromise = orm.call("hr.attendance", "fm_geo_map_config", []).catch(() => ({
      tile_url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }));
  }
  return configPromise;
}

export function statusColor(status) {
  return STATUS_COLOR[status] || STATUS_COLOR.none;
}

export async function createMap(el, orm, options = {}) {
  const L = window.L;
  if (!L) {
    throw new Error("Leaflet did not load");
  }
  const cfg = await mapConfig(orm);
  const map = L.map(el, {
    zoomControl: true,
    attributionControl: true,
    scrollWheelZoom: options.scrollWheelZoom ?? false,
    ...options.leaflet,
  });
  L.tileLayer(cfg.tile_url, { attribution: cfg.attribution, maxZoom: 19 }).addTo(map);
  // A map with no view yet is not "loaded": layers added to it are queued,
  // and anything that asks one of them for its bounds finds no projection
  // to compute them with. Give it a view; the caller fits the real one.
  map.setView([0, 0], 2);
  return map;
}

/** The box around a fence, computed from the numbers alone. */
export function fenceBounds(fence) {
  return window.L.latLng(fence.lat, fence.lng).toBounds(fence.radius * 2);
}

/** A person: a filled dot with a white ring, coloured by the verdict. */
export function personMarker(lat, lng, status) {
  return window.L.circleMarker([lat, lng], {
    radius: 8,
    color: "#ffffff",
    weight: 2,
    fillColor: statusColor(status),
    fillOpacity: 1,
  });
}

/** An office: its centre pin and the circle that is the fence. */
export function fenceLayers(fence, status, { draggable = false } = {}) {
  const L = window.L;
  const color = status ? statusColor(status) : "#4b6cb7";
  const circle = L.circle([fence.lat, fence.lng], {
    radius: fence.radius,
    color,
    weight: 2,
    fillColor: color,
    fillOpacity: 0.12,
  });
  const pin = L.marker([fence.lat, fence.lng], {
    icon: L.divIcon({
      className: "fm_geo_pin",
      html: '<span class="fm_geo_pin_dot"></span>',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    }),
    title: fence.name || "",
    draggable,
  });
  return { circle, pin };
}

export function formatDistance(m) {
  if (m === null || m === undefined || m === false) {
    return "";
  }
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
