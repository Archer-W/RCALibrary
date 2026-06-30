// Single-value stat / KPI card + a stat_group (several cards combined in one
// panel). Supports a color `state`, a highlighted `badge`, a prominent `detail`
// line, an attention-grabbing `alert` badge, and `value_text` (smaller one-line).
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

// Build one stat card from a StatData-shaped object. `opts.value_text`/`opts.title`
// are panel-level fallbacks (the single `stat` panel passes them via options/title).
export function renderStatCard(s, opts = {}) {
  s = s || {};
  const value = s.value == null ? "—" : s.value;
  const textCls = s.value_text || opts.value_text ? " kpi-value-text" : "";
  const children = [
    el(
      "div",
      { class: "kpi-value" + textCls + (s.state ? " state-" + s.state : "") },
      String(value),
      s.unit ? el("span", { class: "kpi-unit" }, " " + s.unit) : null
    ),
  ];
  if (s.badge) children.push(el("div", {}, el("span", { class: "kpi-badge" }, String(s.badge))));
  if (s.detail) children.push(el("div", { class: "kpi-detail" }, String(s.detail)));
  if (s.alert) children.push(el("div", { class: "kpi-alert" }, s.alert));
  children.push(el("div", { class: "kpi-label" }, s.label || opts.title || ""));
  if (s.sub) children.push(el("div", { class: "kpi-sub" }, s.sub));
  return el("div", { class: "kpi" + (s.alert ? " is-alert" : "") }, ...children);
}

registerPanel("stat", (panel, body) => {
  body.appendChild(renderStatCard(panel.stat || {}, {
    value_text: panel.options && panel.options.value_text,
    title: panel.title,
  }));
});

// Several stat cards in one panel (e.g. the header summary row).
registerPanel("stat_group", (panel, body) => {
  const items = (panel.stat_group && panel.stat_group.items) || [];
  if (!items.length) {
    body.appendChild(el("div", { class: "panel-empty" }, "No summary available."));
    return;
  }
  body.appendChild(el("div", { class: "stat-group" }, ...items.map((s) => renderStatCard(s))));
});
