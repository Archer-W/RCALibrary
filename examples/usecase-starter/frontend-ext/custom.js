// Optional use-case custom panels. Served at /ext/custom.js when
// RCA_FRONTEND_EXT_DIR points here. Prefer composing the built-in panel types
// (line/bar/scatter/stat/table/heatmap) from your templates; register a custom
// renderer only when you truly need a new visual — and consider asking the
// framework agent to make broadly-useful panels built-in.
//
// window.RCA = { registerPanel, el, plotly: { draw, baseLayout, baseConfig } }

// Example: a trivial custom panel type "note".
window.RCA.registerPanel("note", (panel, bodyEl) => {
  bodyEl.appendChild(window.RCA.el("div", { class: "panel-markdown" }, panel.markdown || panel.title));
});
