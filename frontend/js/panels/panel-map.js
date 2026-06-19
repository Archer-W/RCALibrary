// Interactive neighborhood map (Step "map"). Sites positioned by lat/lon.
// Default = an OFFLINE blank-canvas scatter (no internet) where SITES are real
// `triangle-up` shapes (colored by trend status) and TICKETS are circles
// (colored by association confidence) — true distinct shapes. The "Street map"
// toggle flips to a muted carto-positron basemap; mapbox renders only circles
// natively (a non-circle needs an async icon that races the tile paint), so
// there sites become filled discs and tickets stay solid circles distinguished
// by color/size. Click a site/tag -> details in the side panel. The view
// auto-fits the checked USIDs / tickets / neighbors.
import { el, clear } from "../core/dom.js";
import { escapeHtml } from "../core/format.js";
import { baseConfig, plotlyReady } from "./plotly-base.js";
import { registerPanel } from "./registry.js";

const TONE_HEX = {
  red: "#c0392b", amber: "#8a5114", green: "#157a3a",
  blue: "#0568AE", grey: "#59667a", purple: "#6f2fc0",
};
const NEIGHBOR_COLOR = "#475569"; // no-trend sites — dark slate (visible on the muted basemap)
const TICKET_COLOR = "#e11d48";   // all ticket markers one red, white-outlined dot centered on the site
// A world-covering white fill that mutes the basemap so the markers stand out.
const DIM_LAYER = {
  sourcetype: "geojson", type: "fill", color: "rgba(255,255,255,0.35)",
  source: { type: "Feature", properties: {}, geometry: { type: "Polygon",
    coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]] } },
};

const fmtDt = (s) => (s == null || s === "" ? null : String(s).slice(0, 16).replace("T", " "));

registerPanel("map", (panel, body) => {
  const data = panel.map || {};
  const features = data.features || [];
  if (!features.length) {
    body.appendChild(el("div", { class: "panel-empty" }, data.notice || "No sites to map."));
    return;
  }
  if (!plotlyReady()) {
    body.appendChild(el("div", { class: "panel-fallback" }, "Plotly.js not loaded — map unavailable."));
    return;
  }
  if (!features.some((f) => f.lat != null && f.lon != null)) {
    body.appendChild(el("div", { class: "panel-empty" }, data.notice || "No mappable sites (no coordinates)."));
    return;
  }

  let useTiles =
    (panel.options && panel.options.map_tiles) ||
    (window.RCA && window.RCA.config && window.RCA.config.mapTiles) ||
    false;
  const baseLat = (data.center && data.center.lat) || features.find((f) => f.lat != null).lat || 0;
  const cosLat = Math.max(0.2, Math.cos((baseLat * Math.PI) / 180));

  let showTickets = true;
  let showNeighbors = true;
  const siteHover = (f) => f.usid + (f.trend_status ? " · " + f.trend_status : " · no trend");

  const chart = el("div", { class: "ts-chart map-chart" });
  const detail = el("div", { class: "map-detail" });

  // Currently-checked, mappable features (with their index in `features`).
  const plotted = () =>
    features
      .map((f, i) => ({ f, i }))
      .filter(({ f }) => f.lat != null && f.lon != null)
      .filter(({ f }) => (f.role === "neighbor" ? showNeighbors : true));

  const siteSymbol = () => (useTiles ? "circle" : "triangle-up");

  // Sites colored by trend status. OFFLINE (default): a true `triangle-up` — a
  // real shape, distinct from the circular tickets. TILES: a filled disc (mapbox
  // only renders circles natively; non-circle needs an async icon that races the
  // tile paint). Split by role-layer (no-trend neighbors behind + smaller, trend/
  // ticket sites in front), then by color so each trace carries one reliable color.
  const SITE_SIZE = 18;  // all sites same (larger) size; role is shown by COLOR, not size

  function siteTraces() {
    const out = [];
    const sym = siteSymbol();
    const layers = [
      { set: plotted().filter(({ f }) => f.role === "neighbor"), size: SITE_SIZE },  // background (drawn first)
      { set: plotted().filter(({ f }) => f.role !== "neighbor"), size: SITE_SIZE },  // foreground
    ];
    for (const { set, size } of layers) {
      if (!set.length) continue;
      const byColor = new Map();
      for (const p of set) {
        const c = p.f.color || NEIGHBOR_COLOR;
        if (!byColor.has(c)) byColor.set(c, []);
        byColor.get(c).push(p);
      }
      for (const [color, g] of byColor) {
        const lats = g.map(({ f }) => f.lat), lons = g.map(({ f }) => f.lon);
        const cd = g.map(({ i }) => ({ kind: "site", fi: i }));
        const hover = g.map(({ f }) => siteHover(f));
        const marker = { size, color, opacity: 1, symbol: sym, line: { color: "#fff", width: 1.5 } };
        const t = { mode: "markers", hovertext: hover, hoverinfo: "text", customdata: cd, marker };
        out.push(useTiles ? { type: "scattermapbox", lat: lats, lon: lons, ...t }
                          : { type: "scatter", x: lons, y: lats, ...t });
      }
    }
    return out;
  }

  // Ticket marker = a single small RED, white-outlined dot drawn at the CENTRE of
  // each site that carries one or more tickets (one mark per site, not per ticket).
  // Red + white outline reads on top of any site color; clicking it lists all of
  // that site's tickets in the side panel. (Per-ticket confidence color stays in
  // the table + the detail panel.)
  function tagTraces() {
    if (!showTickets) return [];
    const g = { lat: [], lon: [], hover: [], cd: [] };
    for (const { f, i } of plotted()) {
      const tks = f.tickets || [];
      if (!tks.length) continue;
      g.lat.push(f.lat);
      g.lon.push(f.lon);
      g.hover.push(tks.length === 1 ? `${tks[0].id} · ${tks[0].type}` : `${tks.length} tickets · USID ${f.usid}`);
      g.cd.push({ kind: "tag", fi: i });
    }
    if (!g.lat.length) return [];
    const marker = { size: 9, color: TICKET_COLOR, symbol: "circle", opacity: 1,
      line: { color: "#fff", width: 2.5 } };  // small red centre dot -> "this site has ticket(s)"
    const t = { mode: "markers", hovertext: g.hover, hoverinfo: "text", customdata: g.cd, marker };
    return [useTiles ? { type: "scattermapbox", lat: g.lat, lon: g.lon, ...t } : { type: "scatter", x: g.lon, y: g.lat, ...t }];
  }

  function bounds() {
    const lats = [], lons = [];
    for (const { f } of plotted()) { lats.push(f.lat); lons.push(f.lon); }
    if (!lats.length) return null;
    return { minLat: Math.min(...lats), maxLat: Math.max(...lats), minLon: Math.min(...lons), maxLon: Math.max(...lons) };
  }

  function fitZoom(b) {
    const pad = 1.15; // ~15% margin around the points; otherwise fill the window
    const lonSpan = Math.max(2e-4, (b.maxLon - b.minLon) * pad);
    const latSpan = Math.max(2e-4, (b.maxLat - b.minLat) * pad);
    // Web-Mercator (512px tiles): lon spans 360°, lat spans 360°·cos(lat) per world width.
    const zLon = Math.log2(360 / lonSpan) + Math.log2(700 / 512);
    const zLat = Math.log2((360 * cosLat) / latSpan) + Math.log2(460 / 512);
    return Math.max(2, Math.min(16, Math.min(zLon, zLat)));
  }

  function buildTraces() {
    return [...siteTraces(), ...tagTraces()];
  }

  function buildLayout() {
    const base = { height: 460, margin: { l: 8, r: 8, t: 8, b: 8 }, showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)", hovermode: "closest" };
    const b = bounds();
    if (useTiles) {
      const center = b ? { lat: (b.minLat + b.maxLat) / 2, lon: (b.minLon + b.maxLon) / 2 } : (data.center || { lat: baseLat, lon: 0 });
      return { ...base, mapbox: { style: "carto-positron", center, zoom: b ? fitZoom(b) : 11, layers: [DIM_LAYER] } };
    }
    const hidden = { showgrid: false, zeroline: false, showticklabels: false, ticks: "", visible: true, autorange: true };
    return { ...base, plot_bgcolor: "#eef3f8",
      xaxis: { ...hidden },
      // equal aspect: 1° lat renders 1/cos(lat) wider than 1° lon (km-correct); autorange fits the checked points
      yaxis: { ...hidden, scaleanchor: "x", scaleratio: 1 / cosLat } };
  }

  function onClick(ev) {
    const cd = ev && ev.points && ev.points[0] && ev.points[0].customdata;
    if (!cd) return;
    const f = features[cd.fi];
    if (!f) return;
    if (cd.kind === "tag") showSiteTickets(f);  // the centre mark -> all of this site's tickets
    else showSite(f);
  }
  // Layer toggles keep the subplot type -> Plotly.react (re-fits via autorange/zoom).
  function redraw() {
    window.Plotly.react(chart, buildTraces(), buildLayout(), baseConfig());
    renderLegend();
  }
  // Basemap switch changes subplot type (scatter <-> mapbox) -> purge + newPlot.
  function switchBasemap(on) {
    useTiles = on;
    window.Plotly.purge(chart);
    window.Plotly.newPlot(chart, buildTraces(), buildLayout(), baseConfig());
    chart.on("plotly_click", onClick);
    renderLegend();
  }
  // Legend tracks the current basemap: site swatch = triangle (offline) / disc (tiles).
  const siteSwatch = (color) => useTiles
    ? el("span", { class: "map-dot", style: `background:${color}` })
    : el("span", { class: "map-tri", style: `color:${color}` });
  function renderLegend() {
    clear(legendBox);
    (data.legend || []).forEach((l) =>
      legendBox.appendChild(el("span", { class: "map-legend-item" }, siteSwatch(l.color), l.label)));
    legendBox.appendChild(el("span", { class: "map-legend-item" },
      el("span", { class: "map-dot map-dot-ticket", style: `background:${TICKET_COLOR}` }), "ticket"));
  }

  // --- detail (right side) ---
  function showSite(f) {
    clear(detail);
    const stateCls = f.color_state ? " state-" + f.color_state : "";
    detail.appendChild(el("div", { class: "map-detail-head" },
      siteSwatch(f.color),
      el("strong", {}, "USID " + f.usid),
      f.trend_status ? el("span", { class: "kpi-value-inline" + stateCls }, f.trend_status) : null));
    const calls = f.calls_known ? f.total_calls : "n/a (no call data)";
    detail.appendChild(el("div", { class: "map-detail-row" }, `# of Calls in anomaly window: ${calls}`));
    if (f.trend_status) {
      detail.appendChild(el("div", { class: "map-detail-row" }, `Trend start: ${fmtDt(f.trend_start) || "—"}`));
      detail.appendChild(el("div", { class: "map-detail-row" }, `Trend close: ${fmtDt(f.trend_close) || "ongoing"}`));
    } else if (f.role === "neighbor") {
      detail.appendChild(el("div", { class: "map-detail-row muted" }, "No trend (nearby site)"));
    }
    if ((f.tickets || []).length) {
      detail.appendChild(el("div", { class: "map-detail-row" }, `${f.tickets.length} ticket(s):`));
      for (const t of f.tickets) {
        detail.appendChild(el("button", { class: "ts-ticket-chip tone-" + (t.tone || "grey"), type: "button",
          onClick: () => showTicket(t) }, `${t.id} · ${t.type}`));
      }
    }
  }

  // Append one ticket's details to a container (shared by single + multi views).
  function ticketDetail(t, into) {
    const c = (txt, tone) => `<span style="color:${TONE_HEX[tone] || TONE_HEX.grey}">${escapeHtml(txt)}</span>`;
    into.appendChild(el("div", { class: "map-detail-row", html: `<strong>${escapeHtml(t.id)}</strong> · ${c(t.type, t.type_tone)}` }));
    into.appendChild(el("div", { class: "map-detail-row", html:
      `status ${c(t.status, t.status_tone)} · impact ${c(t.impact, t.impact_tone)}` }));
    into.appendChild(el("div", { class: "map-detail-row" }, t.event || "—"));
    into.appendChild(el("div", { class: "map-detail-row muted" },
      `Start ${fmtDt(t.start) || "—"} · Close ${fmtDt(t.end) || "ongoing"} · PRT ${fmtDt(t.prt) || "—"}`));
  }

  function showTicket(t) {  // single ticket (from a chip in the site view)
    clear(detail);
    detail.appendChild(el("div", { class: "map-detail-head" },
      el("span", { class: "map-dot", style: `background:${TICKET_COLOR}` }),
      el("strong", {}, "Ticket on USID " + t.usid)));
    ticketDetail(t, detail);
  }

  // All tickets on a site (from clicking the centre ticket mark).
  function showSiteTickets(f) {
    clear(detail);
    const tks = f.tickets || [];
    detail.appendChild(el("div", { class: "map-detail-head" },
      el("span", { class: "map-dot", style: `background:${TICKET_COLOR}` }),
      el("strong", {}, `${tks.length} ticket${tks.length === 1 ? "" : "s"} · USID ${f.usid}`)));
    if (!tks.length) {
      detail.appendChild(el("div", { class: "map-detail-row muted" }, "No tickets."));
      return;
    }
    tks.forEach((t, idx) => {
      if (idx) detail.appendChild(el("hr", { class: "map-detail-sep" }));
      ticketDetail(t, detail);
    });
  }

  // --- controls ---
  function toggle(label, getOn, setOn) {
    const input = el("input", { type: "checkbox", checked: getOn(),
      onChange: (e) => { setOn(e.currentTarget.checked); redraw(); } });
    return el("label", { class: "ts-check" }, input, el("span", {}, label));
  }
  const basemap = el("label", { class: "ts-check", title: "OpenStreetMap/Carto tiles (requires internet)" },
    el("input", { type: "checkbox", checked: useTiles, onChange: (e) => switchBasemap(e.currentTarget.checked) }),
    el("span", {}, "Street map"));
  const legendBox = el("div", { class: "map-legend" });  // filled by renderLegend() (mode-aware)

  const controls = el("div", { class: "ts-controls" },
    el("div", { class: "ts-ctl-group" }, el("span", { class: "ts-ctl-label" }, "Basemap"), basemap),
    el("div", { class: "ts-ctl-group" }, el("span", { class: "ts-ctl-label" }, "Layers"),
      toggle("Ticket tags", () => showTickets, (v) => (showTickets = v)),
      toggle("Nearby (no-trend) sites", () => showNeighbors, (v) => (showNeighbors = v))),
    el("div", { class: "ts-ctl-group" }, legendBox)
  );
  if (data.missing_coords) {
    controls.appendChild(el("div", { class: "map-detail-row muted" },
      `${data.missing_coords} site(s) have no coordinates (not shown).`));
  }

  body.appendChild(controls);
  body.appendChild(el("div", { class: "map-body" }, chart, detail));
  redraw();
  chart.on("plotly_click", onClick);
});
