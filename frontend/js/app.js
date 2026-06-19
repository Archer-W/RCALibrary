// Bootstrap: register panels, load solutions, render the shell, start the router.
import * as store from "./core/store.js";
import * as endpoints from "./api/endpoints.js";
import { startRouter } from "./core/router.js";
import { registerPanel } from "./panels/registry.js";
import { el } from "./core/dom.js";
import { draw, baseLayout, baseConfig } from "./panels/plotly-base.js";

// Import panel modules for their registration side-effects.
import "./panels/panel-charts.js";
import "./panels/panel-kpi.js";
import "./panels/panel-table.js";
import "./panels/panel-fields.js";
import "./panels/panel-timeseries.js";
import "./panels/panel-map.js";
import "./panels/panel-flow.js";
import "./panels/panel-misc.js";

// Public extension API for use-case custom panels (see docs/07). A use-case repo
// serves a module at /ext/custom.js (RCA_FRONTEND_EXT_DIR) that calls
// window.RCA.registerPanel("my_type", (panel, bodyEl) => { ... }).
// window.RCA.config holds boot-time server config (e.g. map tiles).
window.RCA = { registerPanel, el, plotly: { draw, baseLayout, baseConfig }, config: { mapTiles: false } };

async function boot() {
  const root = document.getElementById("app");

  // Boot config (e.g. whether map panels use online tiles).
  try {
    const m = await endpoints.getMeta();
    window.RCA.config.mapTiles = !!m.map_tiles;
  } catch {
    /* defaults already set */
  }

  // Optionally load use-case custom panels before anything renders.
  try {
    await import("/ext/custom.js");
  } catch {
    /* no /ext/custom.js mounted — fine */
  }

  // Load solutions before first render so the sidebar/landing have data.
  try {
    store.set("solutions", await endpoints.listSolutions());
  } catch (e) {
    console.error("Failed to load solutions:", e);
    store.set("solutions", []);
  }

  startRouter(root);

  // Non-blocking: populate the (placeholder) user indicator.
  endpoints.getCurrentUser().then((u) => store.set("user", u)).catch(() => {});
}

document.addEventListener("DOMContentLoaded", boot);
