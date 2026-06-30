// Chart panels (line / bar / scatter / heatmap / pie). The backend already emits
// Plotly-ready traces + layout (incl. anomaly markers + threshold shapes); we
// just merge in the shared theme and draw.
import { el } from "../core/dom.js";
import { draw, baseLayout } from "./plotly-base.js";
import { registerPanel } from "./registry.js";

function chart(panel, body) {
  // Draw into a CHILD host (not the panel body) so the .js-plotly-plot element is a
  // descendant — this is what makes resize() find it and adapt on window resize
  // (matching the timeseries/map panels). Drawing on the body itself missed resize.
  const host = el("div", { class: "chart-host" });
  body.appendChild(host);
  draw(host, panel.traces || [], baseLayout(panel.layout || {}));
}

registerPanel("line", chart);
registerPanel("bar", chart);
registerPanel("scatter", chart);
registerPanel("heatmap", chart);
registerPanel("pie", chart); // backend emits a pie trace (labels + values)
