/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";

/**
 * The Sales Dashboard.
 *
 * The server computes every figure (fm.sales.dashboard.get_data); this
 * component draws them and turns every one of them into a link to the
 * records behind it. Charts are Chart.js from Odoo's own bundle
 * (web.chartjs_lib), so nothing is fetched from a CDN and nothing is
 * vendored.
 *
 * Colours are read from CSS custom properties at draw time, so the charts
 * follow whatever theme the backend is in - including a dark one.
 */

// Series colours, fixed per entity (a state keeps its colour whatever is
// filtered), validated for colour-vision deficiency in both light and dark.
const SERIES = {
    light: { sale: "#2a78d6", draft: "#eb6834", sent: "#4a3aa7", cancel: "#e34948",
             invoiced: "#2a78d6", "to invoice": "#eb6834", no: "#4a3aa7", upselling: "#008300",
             one: "#2a78d6" },
    dark:  { sale: "#3987e5", draft: "#d95926", sent: "#9085e9", cancel: "#e66767",
             invoiced: "#3987e5", "to invoice": "#d95926", no: "#9085e9", upselling: "#008300",
             one: "#3987e5" },
};

const PRESETS = [
    { key: "month", label: _t("This month") },
    { key: "last_month", label: _t("Last month") },
    { key: "quarter", label: _t("This quarter") },
    { key: "year", label: _t("This year") },
    { key: "custom", label: _t("Custom") },
];

function isoDate(d) {
    return d.toISODate();
}

function presetRange(key) {
    const { DateTime } = luxon;
    const now = DateTime.local();
    switch (key) {
        case "last_month": {
            const m = now.minus({ months: 1 });
            return [isoDate(m.startOf("month")), isoDate(m.endOf("month"))];
        }
        case "quarter":
            return [isoDate(now.startOf("quarter")), isoDate(now)];
        case "year":
            return [isoDate(now.startOf("year")), isoDate(now)];
        default:
            return [isoDate(now.startOf("month")), isoDate(now)];
    }
}

export class SalesDashboard extends Component {
    static template = "fm_sales_dashboard.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.refs = {
            trend: useRef("trend"),
            byState: useRef("byState"),
            teams: useRef("teams"),
            salespersons: useRef("salespersons"),
            invoice: useRef("invoice"),
        };
        this.charts = {};
        const [from, to] = presetRange("month");
        this.state = useState({
            loading: true,
            error: null,
            preset: "month",
            dateFrom: from,
            dateTo: to,
            data: null,
            lastRefresh: null,
        });
        this.presets = PRESETS;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        // Redraw whenever fresh data arrived or the theme flipped.
        useEffect(
            () => {
                if (this.state.data) {
                    this.drawCharts();
                }
            },
            () => [this.state.data]
        );
        this.onThemeChange = () => this.state.data && this.drawCharts();
        this.themeObserver = new MutationObserver(this.onThemeChange);
        this.themeObserver.observe(document.body, { attributes: true, attributeFilter: ["class"] });
        this.mq = window.matchMedia("(prefers-color-scheme: dark)");
        this.mq.addEventListener("change", this.onThemeChange);
        onWillUnmount(() => {
            this.themeObserver.disconnect();
            this.mq.removeEventListener("change", this.onThemeChange);
            this.destroyCharts();
        });
    }

    // ── Data ──────────────────────────────────────────────────────────────

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("fm.sales.dashboard", "get_data", [], {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
            });
            this.state.lastRefresh = luxon.DateTime.local().toFormat("HH:mm");
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    setPreset(key) {
        this.state.preset = key;
        if (key !== "custom") {
            [this.state.dateFrom, this.state.dateTo] = presetRange(key);
            this.load();
        }
    }

    onDateChange(field, ev) {
        if (!ev.target.value) {
            return;
        }
        this.state[field] = ev.target.value;
        this.state.preset = "custom";
        if (this.state.dateFrom && this.state.dateTo) {
            this.load();
        }
    }

    // ── Formatting ────────────────────────────────────────────────────────

    get locale() {
        return (localization.code || "en_US").replace("_", "-");
    }

    money(value, { compact = false, symbol = true } = {}) {
        const meta = this.state.data?.meta || {};
        let text;
        try {
            text = new Intl.NumberFormat(this.locale, compact
                ? { notation: "compact", maximumFractionDigits: 1 }
                : { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value || 0);
        } catch (e) {
            text = String(Math.round(value || 0));
        }
        if (!symbol || !meta.currency_symbol) {
            return text;
        }
        return meta.currency_position === "before"
            ? `${meta.currency_symbol} ${text}`
            : `${text} ${meta.currency_symbol}`;
    }

    number(value) {
        try {
            return new Intl.NumberFormat(this.locale).format(value || 0);
        } catch (e) {
            return String(value || 0);
        }
    }

    percent(value) {
        return value === null || value === undefined ? "—" : `${(value >= 0 ? "+" : "")}${value.toFixed(1)}%`;
    }

    /** "+12.4%" style delta between now and the previous period, or null. */
    delta(now, before) {
        if (!before) {
            return null;
        }
        return ((now - before) / before) * 100;
    }

    plural(n, one, many) {
        return `${this.number(n)} ${Math.abs(n) === 1 ? one : many}`;
    }

    share(value, max) {
        return max ? Math.max(2, Math.round((value / max) * 100)) : 0;
    }

    get maxCustomer() {
        return Math.max(0, ...(this.state.data?.top_customers || []).map((c) => c.amount));
    }

    get maxProduct() {
        return Math.max(0, ...(this.state.data?.top_products || []).map((p) => p.amount));
    }

    get periodLabel() {
        const { DateTime } = luxon;
        const f = DateTime.fromISO(this.state.dateFrom);
        const t = DateTime.fromISO(this.state.dateTo);
        return `${f.toFormat("d MMM yyyy")} – ${t.toFormat("d MMM yyyy")}`;
    }

    get prevLabel() {
        const prev = this.state.data?.kpi?.prev;
        if (!prev) {
            return "";
        }
        const { DateTime } = luxon;
        return `${DateTime.fromISO(prev.date_from).toFormat("d MMM")} – ${DateTime.fromISO(prev.date_to).toFormat("d MMM")}`;
    }

    // ── Click-through ─────────────────────────────────────────────────────

    async open(kind, params = {}) {
        const action = await this.orm.call("fm.sales.dashboard", "get_action", [kind], {
            date_from: this.state.dateFrom,
            date_to: this.state.dateTo,
            ...params,
        });
        this.action.doAction(action);
    }

    // ── Charts ────────────────────────────────────────────────────────────

    get isDark() {
        return document.body.classList.contains("fm-dark") ||
            (!document.body.classList.contains("fm-light") && this.mq.matches);
    }

    colors() {
        const root = this.refs.trend.el?.closest(".fm_sd") || document.body;
        const cs = getComputedStyle(root);
        const read = (name, fallback) => (cs.getPropertyValue(name) || "").trim() || fallback;
        return {
            series: SERIES[this.isDark ? "dark" : "light"],
            ink: read("--fm-sd-ink-2", "#6b6b73"),
            grid: read("--fm-sd-hairline", "#e6e6ea"),
            surface: read("--fm-sd-surface", "#ffffff"),
        };
    }

    destroyCharts() {
        for (const chart of Object.values(this.charts)) {
            chart.destroy();
        }
        this.charts = {};
    }

    drawCharts() {
        this.destroyCharts();
        const d = this.state.data;
        const c = this.colors();
        const Chart = window.Chart;
        const font = { family: getComputedStyle(document.body).fontFamily, size: 12 };
        const compact = (v) => this.money(v, { compact: true, symbol: false });
        const tooltipBase = {
            backgroundColor: this.isDark ? "#2b2d36" : "#1c1c22",
            titleColor: "#fff",
            bodyColor: "#e8e8ee",
            padding: 10,
            cornerRadius: 4,
            displayColors: true,
            boxPadding: 4,
        };

        // Monthly trend: three lines, one axis, hairline grid.
        if (this.refs.trend.el) {
            const rows = d.monthly_trend;
            const line = (key, label, color) => ({
                label, data: rows.map((r) => r[key]),
                borderColor: color, backgroundColor: color,
                borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 5,
                pointHoverBackgroundColor: color, pointHoverBorderColor: c.surface, pointHoverBorderWidth: 2,
            });
            this.charts.trend = new Chart(this.refs.trend.el, {
                type: "line",
                data: {
                    labels: rows.map((r) => r.label),
                    datasets: [
                        line("confirmed", _t("Confirmed"), c.series.sale),
                        line("quotation", _t("Quotations"), c.series.draft),
                        line("cancelled", _t("Cancelled"), c.series.cancel),
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { position: "bottom", labels: { color: c.ink, font, usePointStyle: true, pointStyle: "line", boxWidth: 24 } },
                        tooltip: { ...tooltipBase, callbacks: { label: (i) => ` ${i.dataset.label}: ${this.money(i.parsed.y)}` } },
                    },
                    scales: {
                        x: { grid: { display: false }, border: { color: c.grid }, ticks: { color: c.ink, font, maxRotation: 0, autoSkipPadding: 12 } },
                        y: { beginAtZero: true, grid: { color: c.grid, drawTicks: false }, border: { display: false },
                             ticks: { color: c.ink, font, padding: 8, maxTicksLimit: 5, callback: compact } },
                    },
                },
            });
        }

        // Part-to-whole: a ring with a 2px surface gap between segments.
        const ring = (el, rows, keyField, colorOf, onClick) => new Chart(el, {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.amount),
                    backgroundColor: rows.map((r) => colorOf(r[keyField])),
                    borderColor: c.surface, borderWidth: 2, hoverOffset: 4,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: "72%",
                onClick: (_ev, els) => els.length && onClick(rows[els[0].index]),
                plugins: {
                    legend: { display: false },
                    tooltip: { ...tooltipBase, callbacks: { label: (i) => ` ${this.money(i.parsed)} · ${this.number(rows[i.dataIndex].count)}` } },
                },
            },
        });
        if (this.refs.byState.el) {
            this.charts.byState = ring(this.refs.byState.el, d.by_state, "state",
                (k) => c.series[k], (r) => this.open("state", { state: r.state }));
        }
        if (this.refs.invoice.el) {
            this.charts.invoice = ring(this.refs.invoice.el, d.invoice_status, "status",
                (k) => c.series[k], (r) => this.open("invoice_status", { invoice_status: r.status }));
        }

        // Ranked bars: one series, one colour; thin, rounded at the data end.
        const bars = (el, rows, onClick) => new Chart(el, {
            type: "bar",
            data: {
                labels: rows.map((r) => r.name),
                datasets: [{
                    data: rows.map((r) => r.amount),
                    backgroundColor: c.series.one, hoverBackgroundColor: c.series.one,
                    barThickness: 14, borderRadius: 4, borderSkipped: "start",
                }],
            },
            options: {
                indexAxis: "y", responsive: true, maintainAspectRatio: false,
                onClick: (_ev, els) => els.length && onClick(rows[els[0].index]),
                plugins: {
                    legend: { display: false },
                    tooltip: { ...tooltipBase, displayColors: false,
                               callbacks: { label: (i) => ` ${this.money(i.parsed.x)} · ${this.plural(rows[i.dataIndex].order_count, _t("order"), _t("orders"))}` } },
                },
                scales: {
                    x: { beginAtZero: true, grid: { color: c.grid, drawTicks: false }, border: { display: false },
                         ticks: { color: c.ink, font, maxTicksLimit: 5, callback: compact } },
                    y: { grid: { display: false }, border: { display: false }, ticks: { color: c.ink, font, crossAlign: "far" } },
                },
            },
        });
        if (this.refs.teams.el && d.teams.length) {
            this.charts.teams = bars(this.refs.teams.el, d.teams, (r) => this.open("team", { team_id: r.id }));
        }
        if (this.refs.salespersons.el && d.salespersons.length) {
            this.charts.salespersons = bars(this.refs.salespersons.el, d.salespersons, (r) => this.open("salesperson", { user_id: r.id }));
        }
    }
}

registry.category("actions").add("fm_sales_dashboard.dashboard", SalesDashboard);
