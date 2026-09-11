/** @odoo-module **/

import { Component, useRef, useState, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * "You are 1.2 km from Head Office. Why?"
 *
 * Shown by the systray before a check-in from outside a location whose
 * policy asks for a reason. The reason goes back to the server, which
 * keeps it for the check-in that follows.
 */
export class GeoReasonDialog extends Component {
  static template = "fm_attendance_geo.GeoReasonDialog";
  static components = { Dialog };
  static props = {
    message: String,
    confirm: Function,
    cancel: Function,
    close: Function,
  };

  setup() {
    this.state = useState({ reason: "" });
    this.inputRef = useRef("input");
    onMounted(() => this.inputRef.el && this.inputRef.el.focus());
  }

  get title() {
    return _t("Outside the office area");
  }

  get canConfirm() {
    return this.state.reason.trim().length > 0;
  }

  onConfirm() {
    if (!this.canConfirm) {
      return;
    }
    this.props.confirm(this.state.reason.trim());
    this.props.close();
  }

  onCancel() {
    this.props.cancel();
    this.props.close();
  }

  onKeydown(ev) {
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
      this.onConfirm();
    }
  }
}
