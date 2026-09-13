/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * The bell: everything of mine that is due soon or overdue, in the top bar.
 *
 * Refreshed three ways - when the server says an activity of mine changed
 * (bus), every few minutes as a safety net for record deadlines, and when
 * the panel is opened. A toast appears only when the number of alerts has
 * grown since the last look, never on login or reload.
 *
 * The panel is a plain positioned element rather than Odoo's Dropdown:
 * that component's API changed between 17.0 and 18.0, and a panel that
 * is the same code in every version is worth more than a slot.
 */
export class DeadlineSystray extends Component {
    static template = "fm_deadline_alert.Systray";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.buttonRef = useRef("button");
        this.panelRef = useRef("panel");
        this.state = useState({
            open: false,
            loading: false,
            alerts: [],
            settings: { window_hours: 24, toast: true, poll_minutes: 5 },
            panelStyle: "",
        });
        this.known = null; // number of alerts at the last fetch; null before the first

        onWillStart(() => this.fetch({ quiet: true }));
        onMounted(() => {
            try {
                this.env.services.bus_service.subscribe("fm_deadline_alert/refresh", () => this.fetch());
            } catch (e) {
                // No bus: polling still keeps the bell honest.
            }
            this.poll = setInterval(() => this.fetch(), this.state.settings.poll_minutes * 60 * 1000);
            this.onDocClick = (ev) => {
                if (this.state.open && !this.panelRef.el?.contains(ev.target) && !this.buttonRef.el?.contains(ev.target)) {
                    this.close();
                }
            };
            this.onKey = (ev) => ev.key === "Escape" && this.state.open && this.close();
            document.addEventListener("mousedown", this.onDocClick, true);
            document.addEventListener("keydown", this.onKey);
        });
        onWillUnmount(() => {
            clearInterval(this.poll);
            document.removeEventListener("mousedown", this.onDocClick, true);
            document.removeEventListener("keydown", this.onKey);
        });
    }

    // ── Data ──────────────────────────────────────────────────────────────

    async fetch({ quiet = false } = {}) {
        this.state.loading = true;
        try {
            const data = await this.orm.call("fm.deadline.alert", "get_alerts", []);
            const before = this.known;
            this.state.alerts = data.alerts;
            this.state.settings = data.settings;
            this.known = data.alerts.length;
            if (!quiet && before !== null && data.alerts.length > before && data.settings.toast) {
                this.toast(data.alerts);
            }
        } catch (e) {
            // A bell that cannot ring is better than an error dialog every five minutes.
        } finally {
            this.state.loading = false;
        }
    }

    toast(alerts) {
        const overdue = alerts.filter((a) => a.state === "overdue").length;
        const soon = alerts.length - overdue;
        let message;
        if (overdue && soon) {
            message = _t("%(overdue)s overdue, %(soon)s due within %(hours)s hours", { overdue, soon, hours: this.state.settings.window_hours });
        } else if (overdue) {
            message = _t("%(overdue)s overdue", { overdue });
        } else {
            message = _t("%(soon)s due within %(hours)s hours", { soon, hours: this.state.settings.window_hours });
        }
        this.notification.add(message, { title: _t("Deadlines"), type: overdue ? "danger" : "warning", sticky: !!overdue });
    }

    get count() {
        return this.state.alerts.length;
    }

    get overdueCount() {
        return this.state.alerts.filter((a) => a.state === "overdue").length;
    }

    get sections() {
        const by = { overdue: [], today: [], upcoming: [] };
        for (const a of this.state.alerts) {
            (by[a.state] || by.upcoming).push(a);
        }
        return [
            { key: "overdue", label: _t("Overdue"), items: by.overdue },
            { key: "today", label: _t("Today"), items: by.today },
            { key: "upcoming", label: _t("Coming up"), items: by.upcoming },
        ].filter((s) => s.items.length);
    }

    when(a) {
        const d = Math.abs(a.days);
        if (a.state === "overdue") {
            return d === 0 ? _t("earlier today") : d === 1 ? _t("1 day late") : _t("%s days late", d);
        }
        if (a.days === 0) {
            return _t("today");
        }
        if (a.days === 1) {
            return _t("tomorrow");
        }
        return _t("in %s days", a.days);
    }

    // ── Panel ─────────────────────────────────────────────────────────────

    toggle() {
        this.state.open ? this.close() : this.open();
    }

    open() {
        const r = this.buttonRef.el.getBoundingClientRect();
        this.state.panelStyle = `top:${Math.round(r.bottom + 6)}px; right:${Math.max(8, Math.round(window.innerWidth - r.right))}px;`;
        this.state.open = true;
        this.fetch({ quiet: true });
    }

    close() {
        this.state.open = false;
    }

    // ── Actions ───────────────────────────────────────────────────────────

    openRecord(a) {
        this.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: a.res_model,
            res_id: a.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async markDone(ev, a) {
        ev.stopPropagation();
        await this.orm.call("fm.deadline.alert", "mark_activity_done", [a.activity_id]);
        this.state.alerts = this.state.alerts.filter((x) => x.key !== a.key);
        this.known = this.state.alerts.length;
    }

    openAll() {
        this.close();
        this.action.doAction("mail.mail_activity_action");
    }
}

registry.category("systray").add("fm_deadline_alert.systray", { Component: DeadlineSystray }, { sequence: 19 });
