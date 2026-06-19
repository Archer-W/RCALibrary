// Interactive multi-series timeseries panel (Step 2: care-call-volume explorer).
// Every granularity is embedded in the payload, so the granularity switch and
// per-USID toggles are handled entirely client-side via Plotly.react (no
// re-fetch). Lines + data-point markers per granularity; the searched USID is
// emphasized; the aggregate is a solid, area-filled line; and the active-trend
// window (earliest start -> latest end) is shaded behind everything.
import { el } from "../core/dom.js";
import { escapeHtml } from "../core/format.js";
import { baseLayout, baseConfig, plotlyReady } from "./plotly-base.js";
import { registerPanel } from "./registry.js";

// Readable, high-contrast scheme. Anchor = strong blue (no fill); aggregate =
// slate, solid + soft area fill (its fill makes it unmistakable); neighbors =
// distinct categorical hues (none reusing the anchor/aggregate colors).
const ANCHOR_COLOR = "#1565C0";
const AGG_COLOR = "#334155";
const AGG_FILL = "rgba(51,65,85,0.12)";
const ANOMALY_FILL = "rgba(192,57,43,0.10)"; // anomaly (trend-active) window — light transparent red
// Distinct categorical hues, each ≥3:1 contrast on white for legible thin lines.
const NEIGHBOR_PALETTE = ["#D55E00", "#1AA39A", "#9B51E0", "#D6336C", "#2BA84A", "#B8860B", "#E45757", "#008B9E"];
// Ticket overlay band/tag colors, keyed by confidence tone (matches the table).
const TICKET_BAND = {
  green: { fill: "rgba(21,122,58,0.10)", line: "#157a3a" },
  amber: { fill: "rgba(138,81,20,0.10)", line: "#8a5114" },
  grey: { fill: "rgba(89,102,122,0.12)", line: "#59667a" },
};
// Per-field badge text colors (matches the table badges) + confidence tints.
const TONE_HEX = { red: "#c0392b", amber: "#8a5114", green: "#157a3a", blue: "#0568AE", grey: "#59667a", purple: "#6f2fc0" };
const TONE_TINT = { green: "rgba(21,122,58,0.14)", amber: "rgba(224,137,46,0.16)", grey: "rgba(89,102,122,0.13)" };
const toneHex = (t) => TONE_HEX[t] || TONE_HEX.grey;

// Colorful on-chart ticket tag (Plotly text supports <b> and <span style="color">).
// Layout: USID · type / ticket id / dist · status · impact / event name. No time
// — the band's range conveys it.
function ticketTagHtml(tk) {
  const span = (text, tone) => `<span style="color:${toneHex(tone)}">${escapeHtml(text)}</span>`;
  return [
    `<b>${escapeHtml(tk.usid)} · ${span(tk.type, tk.type_tone)}</b>`,
    `<span style="color:#6b7888">${escapeHtml(tk.id)}</span>`,
    `${escapeHtml(tk.dist)} km · ${span(tk.status, tk.status_tone)} · ${span(tk.impact, tk.impact_tone)}`,
    escapeHtml(tk.event),
  ].join("<br>");
}
const ticketTagText = (tk) =>
  `${tk.usid} · ${tk.type}\n${tk.id}\n${tk.dist} km · ${tk.status} · ${tk.impact}\n${tk.event}`;

registerPanel("timeseries", (panel, body) => {
  const ts = panel.timeseries || {};
  const allSeries = ts.series || [];
  if (!allSeries.length) {
    body.appendChild(el("div", { class: "panel-empty" }, ts.notice || "No timeseries data."));
    return;
  }
  if (!plotlyReady()) {
    body.appendChild(el("div", { class: "panel-fallback" }, "Plotly.js not loaded — chart unavailable."));
    return;
  }

  const grans = ts.granularities || [];
  // Stable color per series so toggling lines never reshuffles colors.
  let ni = 0;
  const colors = new Map(
    allSeries.map((s) => [
      s.usid,
      s.role === "anchor"
        ? ANCHOR_COLOR
        : s.role === "aggregate"
        ? AGG_COLOR
        : NEIGHBOR_PALETTE[ni++ % NEIGHBOR_PALETTE.length],
    ])
  );

  // --- state (client-side) ---
  // Default: ONLY the searched USID + the aggregate are selected. If no anchor
  // series exists (real data may not re-emit the searched USID), fall back to
  // the first non-aggregate series so the default is never aggregate-only.
  let gran = ts.default_granularity || (grans[0] && grans[0].key);
  const defaultPick =
    allSeries.find((s) => s.role === "anchor") || allSeries.find((s) => s.role !== "aggregate");
  const visible = new Set(defaultPick ? [defaultPick.usid] : []);
  let showAgg = true;
  // Ticket overlays (Step 3): none shown by default; the user clicks a ticket ID.
  const tickets = ts.tickets || [];
  const selectedTickets = new Set();

  const chart = el("div", { class: "ts-chart" });

  function traceFor(s) {
    const pts = (s.by_gran && s.by_gran[gran]) || { x: [], y: [] };
    const color = colors.get(s.usid);
    // Show the granularity's data points; shrink them when dense (e.g. hourly,
    // ~400+ pts) so markers stay visible without overplotting into a band.
    const markerSize = pts.x.length > 150 ? 3 : s.role === "neighbor" ? 4 : 5;
    const t = {
      type: "scatter",
      mode: "lines+markers", // show the granularity's data points too
      name: s.label,
      x: pts.x,
      y: pts.y,
      marker: { size: markerSize, color },
    };
    if (s.role === "anchor") {
      t.line = { color, width: 3 };
    } else if (s.role === "aggregate") {
      t.line = { color, width: 2.6 }; // solid
      t.fill = "tozeroy";
      t.fillcolor = AGG_FILL;
    } else {
      t.line = { color, width: 1.8 };
    }
    return t;
  }

  function redraw() {
    // aggregate drawn first so its fill sits behind the line traces
    const chosen = allSeries.filter((s) => (s.role === "aggregate" ? showAgg : visible.has(s.usid)));
    chosen.sort((a, b) => (a.role === "aggregate" ? -1 : b.role === "aggregate" ? 1 : 0));
    const traces = chosen.map(traceFor);

    const win = (ts.windows && ts.windows[gran]) || {};
    const span = ts.trend_span;
    const shapes = [];
    const annotations = [];
    if (span && span.start && span.end) {
      shapes.push({
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: span.start,
        x1: span.end,
        y0: 0,
        y1: 1,
        fillcolor: ANOMALY_FILL,
        line: { width: 0 },
        layer: "below",
      });
      annotations.push({
        xref: "x",
        yref: "paper",
        x: span.end,
        y: 0.98, // inside the plot (the 12px top margin would clip it otherwise)
        xanchor: "right",
        yanchor: "top",
        text: "anomaly window",
        showarrow: false,
        font: { size: 14, color: "#c0392b" },
        bgcolor: "rgba(255,255,255,0.75)", // legible over the lines/shade
        borderpad: 3,
      });
    }
    // Selected ticket overlays: a colored band over the event window + a tag.
    let ti = 0;
    for (const id of selectedTickets) {
      const tk = tickets.find((t) => t.id === id);
      if (!tk || !tk.start) continue;
      const band = TICKET_BAND[tk.tone] || TICKET_BAND.grey;
      const end = tk.end || win.end || tk.start; // ongoing -> extend to window edge
      shapes.push({
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: tk.start,
        x1: end,
        y0: 0,
        y1: 1,
        fillcolor: band.fill,
        line: { color: band.line, width: 1, dash: "dot" },
        layer: "below",
      });
      annotations.push({
        xref: "x",
        yref: "paper",
        x: tk.start,
        y: 0.98 - (ti % 3) * 0.17, // stagger so overlapping tags stay readable
        xanchor: "left",
        yanchor: "top",
        align: "left",
        text: ticketTagHtml(tk),
        showarrow: false,
        bordercolor: band.line,
        borderwidth: 2,
        borderpad: 7,
        bgcolor: TONE_TINT[tk.tone] || TONE_TINT.grey,
        font: { size: 13, color: "#1a2330" },
      });
      ti++;
    }
    const layout = baseLayout({
      height: 380,
      showlegend: false, // the checkboxes (with swatches) are the legend + control
      yaxis: { title: ts.y_title || "" },
      xaxis: win.start && win.end ? { range: [win.start, win.end] } : {},
      shapes,
      annotations,
    });
    window.Plotly.react(chart, traces, layout, baseConfig());
  }

  // --- granularity switcher ---
  const granRow = el(
    "div",
    { class: "ts-gran" },
    ...grans.map((g) =>
      el(
        "button",
        {
          class: "ts-gran-btn" + (g.key === gran ? " active" : ""),
          type: "button",
          onClick: (e) => {
            gran = g.key;
            granRow.querySelectorAll(".ts-gran-btn").forEach((b) => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            redraw();
          },
        },
        g.label
      )
    )
  );

  // --- USID toggles (+ aggregate) ---
  function checkRow(s) {
    const isAgg = s.role === "aggregate";
    const input = el("input", {
      type: "checkbox",
      checked: isAgg ? showAgg : visible.has(s.usid),
      onChange: (e) => {
        const on = e.currentTarget.checked;
        if (isAgg) showAgg = on;
        else if (on) visible.add(s.usid);
        else visible.delete(s.usid);
        redraw();
      },
    });
    const swatch = el("span", { class: "ts-swatch", style: `background:${colors.get(s.usid)}` });
    return el(
      "label",
      { class: "ts-check" + (isAgg ? " ts-check-agg" : "") },
      input,
      swatch,
      el("span", {}, s.label)
    );
  }
  const aggSeries = allSeries.find((s) => s.role === "aggregate");
  const checksRow = el(
    "div",
    { class: "ts-usids" },
    ...allSeries.filter((s) => s.role !== "aggregate").map(checkRow),
    aggSeries ? checkRow(aggSeries) : null
  );

  const controlGroups = [
    el("div", { class: "ts-ctl-group" }, el("span", { class: "ts-ctl-label" }, "Granularity"), granRow),
    el("div", { class: "ts-ctl-group" }, el("span", { class: "ts-ctl-label" }, "USIDs"), checksRow),
  ];

  // --- ticket toggles (off by default; click a ticket ID to overlay it) ---
  if (tickets.length) {
    const chipRow = el(
      "div",
      { class: "ts-tickets" },
      ...tickets.map((tk) =>
        el(
          "button",
          {
            class: "ts-ticket-chip tone-" + (tk.tone || "grey"),
            type: "button",
            title: ticketTagText(tk), // hover preview of the ticket
            onClick: (e) => {
              if (selectedTickets.has(tk.id)) selectedTickets.delete(tk.id);
              else selectedTickets.add(tk.id);
              e.currentTarget.classList.toggle("active");
              redraw();
            },
          },
          tk.id
        )
      )
    );
    controlGroups.push(
      el("div", { class: "ts-ctl-group" }, el("span", { class: "ts-ctl-label" }, "Tickets"), chipRow)
    );
  }

  body.appendChild(el("div", { class: "ts-controls" }, ...controlGroups));
  body.appendChild(chart);
  redraw();
});
