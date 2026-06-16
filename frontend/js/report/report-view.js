// Renders a report payload: header, anomaly banner, and the responsive panel grid.
import { el, clear } from "../core/dom.js";
import { renderPanel } from "../panels/registry.js";
import { renderAnomalyBanner } from "./anomaly-summary.js";

export function renderReport(report, container) {
  clear(container);

  container.appendChild(
    el(
      "div",
      { class: "report-header" },
      el("h2", {}, report.title || "Report"),
      report.generated_at
        ? el("span", { class: "report-time" }, "Generated " + formatTime(report.generated_at))
        : null
    )
  );

  const banner = el("div", { class: "report-banner" });
  container.appendChild(banner);
  renderAnomalyBanner(report, banner);

  if (report.warnings && report.warnings.length) {
    container.appendChild(
      el("div", { class: "banner banner-warn" }, "Warnings: " + report.warnings.join("; "))
    );
  }

  const grid = el("div", { class: "panel-grid" });
  container.appendChild(grid);
  const instances = (report.panels || []).map((p) => renderPanel(p, grid));

  const onResize = () => instances.forEach((i) => i.resize && i.resize());
  window.addEventListener("resize", onResize);
  return { destroy: () => window.removeEventListener("resize", onResize) };
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
