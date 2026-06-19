// Data-grid panel (pure DOM). A cell is either a plain scalar (rendered as text)
// or a { value, tone } object (rendered as a color-coded badge). Tones:
// red / amber / green / blue / grey / purple — see .cell-badge in panels.css.
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

function renderCell(cell) {
  if (cell && typeof cell === "object" && !Array.isArray(cell)) {
    const tone = cell.tone ? " tone-" + cell.tone : "";
    return el("span", { class: "cell-badge" + tone }, cell.value == null ? "" : String(cell.value));
  }
  return cell == null ? "" : String(cell);
}

registerPanel("table", (panel, body) => {
  const t = panel.table || { columns: [], rows: [] };
  if (!t.rows.length) {
    body.appendChild(el("div", { class: "panel-empty" }, t.notice || "No rows."));
    return;
  }
  const thead = el("thead", {}, el("tr", {}, ...t.columns.map((c) => el("th", {}, c))));
  const tbody = el(
    "tbody",
    {},
    ...t.rows.map((r) => el("tr", {}, ...r.map((cell) => el("td", {}, renderCell(cell)))))
  );
  body.appendChild(el("div", { class: "table-wrap" }, el("table", { class: "data-table" }, thead, tbody)));
});
