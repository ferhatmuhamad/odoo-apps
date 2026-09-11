/** @odoo-module **/

import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { GeoReasonDialog } from "./geo_reason_dialog";

/**
 * The systray check-in, with the geofence asked first.
 *
 * Odoo's own menu gets the position and then calls `checking(lat, lng)`.
 * That method is patched, not replaced: it is where the exact coordinates
 * about to be sent are known, and it is identical in 17.0, 18.0 and 19.0.
 *
 * The pre-check is advisory. It exists so the person sees "you are 1.2 km
 * from Head Office" and a place to type a reason BEFORE the check-in,
 * instead of an error after it. The server judges the real check-in again
 * regardless of what happens here.
 */

/**
 * The position the browser produced a moment ago for Odoo's own call,
 * with the fields Odoo does not send: accuracy, speed and the fix's age.
 * `maximumAge` lets the browser hand back that same fix instead of
 * starting a new one, so this costs nothing when it works and is skipped
 * when it does not.
 */
function recentPosition() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      return resolve({});
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({
        accuracy: pos.coords.accuracy,
        speed: pos.coords.speed,
        position_time: pos.timestamp,
      }),
      () => resolve({}),
      { maximumAge: 60000, timeout: 3000, enableHighAccuracy: true }
    );
  });
}

patch(ActivityMenu.prototype, {
  setup() {
    super.setup(...arguments);
    this.fmGeoOrm = useService("orm");
    this.fmGeoDialog = useService("dialog");
  },

  async checking(latitude = false, longitude = false) {
    let extra = {};
    if (latitude && longitude) {
      extra = await recentPosition();
    }
    let verdict;
    try {
      verdict = await this.fmGeoOrm.call("hr.employee", "fm_geo_precheck", [], {
        latitude,
        longitude,
        ...extra,
      });
    } catch (e) {
      // Could not ask. Let Odoo proceed; the server still decides.
      return super.checking(latitude, longitude);
    }

    if (verdict.action === "block") {
      this.notification.add(verdict.message, {
        title: _t("Attendance"),
        type: "danger",
        sticky: true,
      });
      this._attendanceInProgress = false;
      return;
    }

    if (verdict.action === "reason") {
      const reason = await new Promise((resolve) => {
        this.fmGeoDialog.add(GeoReasonDialog, {
          message: verdict.message,
          confirm: resolve,
          cancel: () => resolve(null),
        });
      });
      if (!reason) {
        this._attendanceInProgress = false;
        return;
      }
      try {
        await this.fmGeoOrm.call("hr.employee", "fm_geo_precheck", [], {
          latitude,
          longitude,
          ...extra,
          reason,
        });
      } catch (e) {
        this._attendanceInProgress = false;
        throw e;
      }
    }

    return super.checking(latitude, longitude);
  },
});
