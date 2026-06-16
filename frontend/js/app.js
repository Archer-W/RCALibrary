// Bootstrap: register panels, load solutions, render the shell, start the router.
import * as store from "./core/store.js";
import * as endpoints from "./api/endpoints.js";
import { startRouter } from "./core/router.js";

// Import panel modules for their registration side-effects.
import "./panels/panel-charts.js";
import "./panels/panel-kpi.js";
import "./panels/panel-table.js";
import "./panels/panel-misc.js";

async function boot() {
  const root = document.getElementById("app");

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
