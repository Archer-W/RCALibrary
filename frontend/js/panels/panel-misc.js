// Markdown panel + the forward-compatible fallback for unknown types.
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("markdown", (panel, body) => {
  body.appendChild(el("div", { class: "panel-markdown" }, panel.markdown || ""));
});

registerPanel("_unknown", (panel, body) => {
  body.appendChild(el("div", { class: "panel-fallback" }, `Unsupported panel type: ${panel.type}`));
});
