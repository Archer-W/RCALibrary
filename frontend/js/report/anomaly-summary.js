// Aggregates the report's anomaly roll-up into a banner.
import { el } from "../core/dom.js";

export function renderAnomalyBanner(report, container) {
  const summary = report.summary || {};
  const total = summary.total_anomalies || 0;
  const sev = summary.severity_counts || {};

  if (total === 0) {
    container.appendChild(el("div", { class: "banner banner-ok" }, "✓ No anomalies detected."));
    return;
  }

  const chips = Object.entries(sev).map(([s, n]) =>
    el("span", { class: `sev-chip sev-${s}` }, `${n} ${s}`)
  );
  container.appendChild(
    el(
      "div",
      { class: "banner banner-warn" },
      el("strong", {}, `⚠ ${total} anomal${total > 1 ? "ies" : "y"} detected`),
      el("span", { class: "banner-chips" }, ...chips)
    )
  );
}
