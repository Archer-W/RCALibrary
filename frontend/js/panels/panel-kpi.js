// Single-value stat / KPI card (pure DOM, no Plotly).
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("stat", (panel, body) => {
  const s = panel.stat || {};
  const value = s.value == null ? "—" : s.value;
  body.appendChild(
    el(
      "div",
      { class: "kpi" },
      el(
        "div",
        { class: "kpi-value" },
        String(value),
        s.unit ? el("span", { class: "kpi-unit" }, " " + s.unit) : null
      ),
      el("div", { class: "kpi-label" }, s.label || panel.title)
    )
  );
});
