// Markdown panel (basic: **bold** + line breaks) + the forward-compatible
// fallback for unknown types.
import { el } from "../core/dom.js";
import { mdBlock } from "../core/format.js";
import { registerPanel } from "./registry.js";

registerPanel("markdown", (panel, body) => {
  body.appendChild(el("div", { class: "panel-markdown", html: mdBlock(panel.markdown || "") }));
});

registerPanel("_unknown", (panel, body) => {
  body.appendChild(el("div", { class: "panel-fallback" }, `Unsupported panel type: ${panel.type}`));
});
