/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";

/**
 * The Sales Scoreboard: a screen on the wall.
 *
 * One salesperson at a time, sliding to the next on a timer, ending on a
 * ranking of everyone; the figures refresh on a second timer. The server
 * does the arithmetic (fm.sales.scoreboard.get_data); this only draws, and
 * turns every figure into a link to the leads behind it.
 *
 * Deliberately one theme, dark: it is built for a television in a sales
 * room, where a white page is a lamp.
 */

// Won / In progress / Lost, stacked in that order so green and red are
// never neighbours; validated for colour-vision deficiency on the board's
// surface. The target line is the one warm accent.
const COLORS = { won: "#2fae6c", open: "#9085e9", lost: "#e66767", target: "#f2c14e",
                 surface: "#141827", ink: "#e9ebf4", ink2: "#9aa0bb", grid: "#252a40" };

export class SalesScoreboard extends Component {
    static template = "fm_sales_scoreboard.Board";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.chartRef = useRef("chart");
        this.rootRef = useRef("root");
        this.chart = null;
        this.slideTimer = null;
        this.refreshTimer = null;
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            mode: "month",       // "month" (12 months of the year) | "day" (days of the month)
            metric: "value",     // "value" | "count"
            year: null,
            month: null,
            teamId: "",
            creatorId: "",
            active: 0,           // index into salespersons; === length means the ranking slide
            paused: false,
            fullscreen: false,
            lastRefresh: "",
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load(true);
        });
        onMounted(() => {
            this.onKey = (ev) => this.onKeydown(ev);
            window.addEventListener("keydown", this.onKey);
            this.onFs = () => (this.state.fullscreen = !!document.fullscreenElement);
            document.addEventListener("fullscreenchange", this.onFs);
            this.startTimers();
        });
        onWillUnmount(() => {
            this.stopTimers();
            window.removeEventListener("keydown", this.onKey);
            document.removeEventListener("fullscreenchange", this.onFs);
            this.chart && this.chart.destroy();
        });
        useEffect(
            () => this.draw(),
            () => [this.state.data, this.state.active, this.state.metric]
        );
    }

    // ── Data ──────────────────────────────────────────────────────────────

    async load(first = false) {
        this.state.loading = true;
        try {
            const data = await this.orm.call("fm.sales.scoreboard", "get_data", [], {
                mode: this.state.mode,
                year: this.state.year,
                month: this.state.month,
                team_id: this.state.teamId || false,
                creator_id: this.state.creatorId || false,
            });
            this.state.data = data;
            this.state.year = data.year;
            this.state.month = data.month;
            this.state.error = "";
            if (this.state.active > data.salespersons.length) {
                this.state.active = 0;
            }
            this.state.lastRefresh = luxon.DateTime.local().toFormat("HH:mm:ss");
            if (!first) {
                this.startTimers();
            }
        } catch (e) {
            this.state.error = (e.data && e.data.message) || e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    get people() {
        return this.state.data ? this.state.data.salespersons : [];
    }

    get isRanking() {
        return this.people.length > 0 && this.state.active >= this.people.length;
    }

    get current() {
        return this.isRanking ? null : this.people[this.state.active];
    }

    get ranking() {
        return [...this.people].sort((a, b) => b.summary.closed_value - a.summary.closed_value);
    }

    get maxClosed() {
        return Math.max(0, ...this.people.map((p) => p.summary.closed_value));
    }

    get slots() {
        return this.people.length + (this.people.length ? 1 : 0);
    }

    // ── Timers, keys, fullscreen ──────────────────────────────────────────

    startTimers() {
        this.stopTimers();
        const cfg = this.state.data ? this.state.data.config : { slide_seconds: 10, refresh_seconds: 15 };
        this.slideTimer = setInterval(() => !this.state.paused && this.step(1), cfg.slide_seconds * 1000);
        this.refreshTimer = setInterval(() => this.load(), cfg.refresh_seconds * 1000);
    }

    stopTimers() {
        clearInterval(this.slideTimer);
        clearInterval(this.refreshTimer);
        this.slideTimer = this.refreshTimer = null;
    }

    step(dir) {
        if (!this.slots) {
            return;
        }
        this.state.active = (this.state.active + dir + this.slots) % this.slots;
    }

    select(index) {
        this.state.active = index;
        this.startTimers(); // a hand on the board restarts the clock
    }

    togglePause() {
        this.state.paused = !this.state.paused;
    }

    onKeydown(ev) {
        if (ev.target && ["INPUT", "SELECT", "TEXTAREA"].includes(ev.target.tagName)) {
            return;
        }
        if (ev.key === "ArrowRight") { this.step(1); this.startTimers(); }
        else if (ev.key === "ArrowLeft") { this.step(-1); this.startTimers(); }
        else if (ev.key === " ") { ev.preventDefault(); this.togglePause(); }
        else if (ev.key === "f") { this.toggleFullscreen(); }
    }

    toggleFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else if (this.rootRef.el && this.rootRef.el.requestFullscreen) {
            this.rootRef.el.requestFullscreen();
        }
    }

    // ── Filters ───────────────────────────────────────────────────────────

    async onFilter(field, ev) {
        this.state[field] = ev.target.value;
        this.state.active = 0;
        await this.load();
    }

    onMetric(metric) {
        this.state.metric = metric;
    }

    // ── Formatting ────────────────────────────────────────────────────────

    get locale() {
        return (localization.code || "en_US").replace("_", "-");
    }

    money(v, compact = true) {
        const d = this.state.data || {};
        let text;
        try {
            text = new Intl.NumberFormat(this.locale, compact
                ? { notation: "compact", maximumFractionDigits: 1 }
                : { maximumFractionDigits: 0 }).format(v || 0);
        } catch (e) {
            text = String(Math.round(v || 0));
        }
        if (!d.currency_symbol) {
            return text;
        }
        return d.currency_position === "after" ? `${text} ${d.currency_symbol}` : `${d.currency_symbol} ${text}`;
    }

    number(v) {
        try { return new Intl.NumberFormat(this.locale).format(v || 0); } catch (e) { return String(v || 0); }
    }

    metricValue(sp, key) {
        const s = sp.summary;
        return this.state.metric === "count" ? this.number(s[key]) : this.money(s[key + "_value"]);
    }

    initials(name) {
        return (name || "").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
    }

    pct(v) {
        return v === null || v === undefined ? "—" : `${v}%`;
    }

    // ── Click-through ─────────────────────────────────────────────────────

    async open(sp, kind, bucket = null) {
        try {
            const action = await this.orm.call("fm.sales.scoreboard", "get_lead_action", [sp.user_id, kind], {
                mode: this.state.mode, year: this.state.year, month: this.state.month,
                bucket, creator_id: this.state.creatorId || false,
            });
            this.action.doAction(action);
        } catch (e) {
            // An RPCError keeps the server's sentence in data.message; its own
            // message is the generic "Odoo Server Error".
            this.notification.add((e.data && e.data.message) || e.message || String(e), { type: "warning" });
        }
    }

    // ── Chart ─────────────────────────────────────────────────────────────

    draw() {
        const el = this.chartRef.el;
        const sp = this.current;
        const d = this.state.data;
        if (!el || !sp || !d || !window.Chart) {
            if (this.chart) { this.chart.destroy(); this.chart = null; }
            return;
        }
        const Chart = window.Chart;
        const byCount = this.state.metric === "count";
        const src = byCount ? sp.series : sp.values;
        const font = { family: getComputedStyle(document.body).fontFamily, size: 13 };
        const fmt = (v) => (byCount ? this.number(v) : this.money(v));
        const bar = (key, label, color) => ({
            type: "bar", label, data: src[key], backgroundColor: color, hoverBackgroundColor: color,
            borderColor: COLORS.surface, borderWidth: 2, borderSkipped: false, stack: "cohort",
            maxBarThickness: 28, meta: key,
        });
        const datasets = [bar("won", _t("Won"), COLORS.won), bar("open", _t("In progress"), COLORS.open), bar("lost", _t("Lost"), COLORS.lost)];
        if (!byCount && d.target > 0) {
            datasets.push({
                type: "line", label: _t("Target"), data: d.labels.map(() => d.target_line),
                borderColor: COLORS.target, borderWidth: 2, borderDash: [6, 6], pointRadius: 0, pointHoverRadius: 0,
                stack: "target", meta: "target",
            });
        }
        const config = {
            data: { labels: d.labels, datasets },
            options: {
                responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
                interaction: { mode: "index", intersect: false },
                onClick: (_ev, els) => {
                    const hit = els.find((e) => datasets[e.datasetIndex].meta !== "target");
                    if (!hit) { return; }
                    const kind = { won: "created_won", open: "created_open", lost: "created_lost" }[datasets[hit.datasetIndex].meta];
                    this.open(sp, kind, hit.index);
                },
                plugins: {
                    legend: { position: "bottom", labels: { color: COLORS.ink2, font, usePointStyle: true, pointStyle: "rectRounded", boxWidth: 10 } },
                    tooltip: {
                        backgroundColor: "#0c0f1c", titleColor: COLORS.ink, bodyColor: COLORS.ink, padding: 10, cornerRadius: 4,
                        filter: (i) => datasets[i.datasetIndex].meta !== "target" || i.dataIndex === 0,
                        callbacks: { label: (i) => ` ${i.dataset.label}: ${fmt(i.parsed.y)}` },
                    },
                },
                scales: {
                    x: { stacked: true, grid: { display: false }, border: { color: COLORS.grid }, ticks: { color: COLORS.ink2, font, maxRotation: 0, autoSkipPadding: 10 } },
                    y: { stacked: true, beginAtZero: true, grid: { color: COLORS.grid, drawTicks: false }, border: { display: false },
                         ticks: { color: COLORS.ink2, font, padding: 8, maxTicksLimit: 5, callback: (v) => byCount ? this.number(v) : this.money(v) } },
                },
            },
        };
        if (this.chart && this.chart.canvas === el) {
            this.chart.data = config.data;
            this.chart.options = config.options;
            this.chart.update();
        } else {
            this.chart && this.chart.destroy();
            this.chart = new Chart(el, config);
        }
    }
}

registry.category("actions").add("fm_sales_scoreboard.board", SalesScoreboard);
