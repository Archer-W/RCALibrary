// Chart panels (line / bar / scatter / heatmap). The backend already emits
// Plotly-ready traces + layout (incl. anomaly markers + threshold shapes); we
// just merge in the shared theme and draw.
import { draw, baseLayout } from "./plotly-base.js";
import { registerPanel } from "./registry.js";

function chart(panel, body) {
  draw(body, panel.traces || [], baseLayout(panel.layout || {}));
}

registerPanel("line", chart);
registerPanel("bar", chart);
registerPanel("scatter", chart);
registerPanel("heatmap", chart);
