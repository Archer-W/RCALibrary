// Single-value stat / KPI card (pure DOM, no Plotly). Supports a color `state`
// (good/bad/neutral) on the value, an optional `sub` line, and a prominent
// attention-grabbing `alert` badge.
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("stat", (panel, body) => {
  const s = panel.stat || {};
  const value = s.value == null ? "—" : s.value;
  // options.value_text: a textual value (e.g. a date) — render smaller + no-wrap
  // so it stays on one line and doesn't make the box taller than number stats.
  const textCls = panel.options && panel.options.value_text ? " kpi-value-text" : "";
  const children = [
    el(
      "div",
      { class: "kpi-value" + textCls + (s.state ? " state-" + s.state : "") },
      String(value),
      s.unit ? el("span", { class: "kpi-unit" }, " " + s.unit) : null
    ),
  ];
  // highlighted pill (e.g. the root-cause ticket #) + a prominent, non-muted detail line
  if (s.badge) children.push(el("div", {}, el("span", { class: "kpi-badge" }, String(s.badge))));
  if (s.detail) children.push(el("div", { class: "kpi-detail" }, String(s.detail)));
  if (s.alert) children.push(el("div", { class: "kpi-alert" }, s.alert));
  children.push(el("div", { class: "kpi-label" }, s.label || panel.title));
  if (s.sub) children.push(el("div", { class: "kpi-sub" }, s.sub));
  body.appendChild(el("div", { class: "kpi" + (s.alert ? " is-alert" : "") }, ...children));
});
