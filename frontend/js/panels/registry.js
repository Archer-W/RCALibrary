// Panel dispatcher — the reuse keystone. Backend reports compose declaratively
// from registered panel types; renderPanel(panelSpec, container) draws each one.
import { el } from "../core/dom.js";
import { plotlyReady } from "./plotly-base.js";

const renderers = new Map();

export function registerPanel(type, fn) {
  renderers.set(type, fn);
}

const SEV_ORDER = ["critical", "high", "bad", "medium", "warn", "low", "info"];

function topSeverity(counts) {
  for (const s of SEV_ORDER) if (counts[s]) return s;
  return "warn";
}

export function renderPanel(panel, container) {
  const counts = (panel.anomalies && panel.anomalies.severity_counts) || {};
  const flagged = Object.values(counts).reduce((a, b) => a + b, 0);
  const chip = flagged
    ? el("span", { class: "panel-chip sev-" + topSeverity(counts) }, `${flagged} flagged`)
    : null;

  const body = el("div", { class: "panel-body" });
  const card = el(
    "div",
    { class: `panel panel-${panel.width || "half"}`, id: `panel-${panel.id}` },
    el("div", { class: "panel-head" }, el("h3", { class: "panel-title" }, panel.title), chip),
    body
  );

  const fn = renderers.get(panel.type) || renderers.get("_unknown");
  try {
    fn(panel, body);
  } catch (e) {
    body.innerHTML = `<div class="panel-fallback">Render error: ${e.message}</div>`;
  }

  container.appendChild(card);
  return {
    el: card,
    resize() {
      const plot = body.querySelector(".js-plotly-plot");
      if (plot && plotlyReady()) window.Plotly.Plots.resize(plot);
    },
  };
}
