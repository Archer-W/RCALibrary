// Data-grid panel (pure DOM).
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("table", (panel, body) => {
  const t = panel.table || { columns: [], rows: [] };
  if (!t.rows.length) {
    body.appendChild(el("div", { class: "panel-empty" }, "No rows."));
    return;
  }
  const thead = el("thead", {}, el("tr", {}, ...t.columns.map((c) => el("th", {}, c))));
  const tbody = el(
    "tbody",
    {},
    ...t.rows.map((r) =>
      el("tr", {}, ...r.map((cell) => el("td", {}, cell == null ? "" : String(cell))))
    )
  );
  body.appendChild(el("div", { class: "table-wrap" }, el("table", { class: "data-table" }, thead, tbody)));
});
