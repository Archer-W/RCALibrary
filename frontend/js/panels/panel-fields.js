// Field-grid panel: one box per value (Trend ID, USID, status, duration, ...).
// A box can be color-coded via `state` (good/warn/bad/neutral -> green/orange/
// red/grey) — used e.g. for the trend status. When there are no items, the
// `notice` is shown instead (e.g. a "trend not found" message).
import { el } from "../core/dom.js";
import { mdBlock } from "../core/format.js";
import { registerPanel } from "./registry.js";

registerPanel("fields", (panel, body) => {
  const data = panel.fields || {};
  const items = data.items || [];

  if (!items.length) {
    body.appendChild(el("div", { class: "panel-empty", html: mdBlock(data.notice || "No data.") }));
    return;
  }

  const grid = el("div", { class: "field-grid" });
  for (const it of items) {
    const cls = "field-box" + (it.state ? " state-" + it.state : "");
    grid.appendChild(
      el(
        "div",
        { class: cls },
        el("div", { class: "field-label" }, it.label || ""),
        el("div", { class: "field-value" }, it.value == null ? "—" : String(it.value)),
        it.sub ? el("div", { class: "field-sub" }, it.sub) : null
      )
    );
  }
  body.appendChild(grid);
});
