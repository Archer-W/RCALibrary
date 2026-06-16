// Shared Plotly theme + a draw() wrapper that degrades gracefully if Plotly is absent.

function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function colorway() {
  return [
    cssVar("--att", "#00A8E0"),
    cssVar("--att-deep", "#0568AE"),
    cssVar("--good", "#1a9e4b"),
    cssVar("--warn", "#e0892e"),
    cssVar("--bad", "#c0392b"),
    cssVar("--att-navy", "#002A5C"),
  ];
}

export function baseLayout(overrides = {}) {
  return {
    font: { family: cssVar("--font", "Inter, sans-serif"), size: 12, color: cssVar("--ink", "#1a2330") },
    colorway: colorway(),
    margin: { l: 56, r: 18, t: 12, b: 48 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: true,
    legend: { orientation: "h", y: -0.25 },
    height: 320,
    ...overrides,
  };
}

export function baseConfig() {
  return { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
}

export function plotlyReady() {
  return typeof window.Plotly !== "undefined";
}

export function draw(bodyEl, traces, layout) {
  if (!plotlyReady()) {
    bodyEl.innerHTML =
      '<div class="panel-fallback">Plotly.js not loaded — charts unavailable. ' +
      "Vendor it to <code>frontend/vendor/plotly.min.js</code>.</div>";
    return;
  }
  window.Plotly.newPlot(bodyEl, traces, layout, baseConfig());
}
