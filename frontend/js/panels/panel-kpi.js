// Single-value stat / KPI card (pure DOM, no Plotly). Supports a color `state`
// (good/bad/neutral) on the value and an optional `sub` line.
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("stat", (panel, body) => {
  const s = panel.stat || {};
  const value = s.value == null ? "—" : s.value;
  const children = [
    el(
      "div",
      { class: "kpi-value" + (s.state ? " state-" + s.state : "") },
      String(value),
      s.unit ? el("span", { class: "kpi-unit" }, " " + s.unit) : null
    ),
    el("div", { class: "kpi-label" }, s.label || panel.title),
  ];
  if (s.sub) children.push(el("div", { class: "kpi-sub" }, s.sub));
  body.appendChild(el("div", { class: "kpi" }, ...children));
});
