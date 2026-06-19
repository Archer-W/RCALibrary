// Static workflow / process diagram (pure DOM, no Plotly). Renders a left-to-right
// sequence of stages from `options.stages`; steps within a stage run in parallel.
// Each stage: { title, steps: [string, ...] }  (a single-step stage may use `step`).
// Optional `options.caption` is shown beneath the flow.
import { el } from "../core/dom.js";
import { registerPanel } from "./registry.js";

registerPanel("flow", (panel, body) => {
  const o = panel.options || {};
  const stages = o.stages || [];
  if (!stages.length) {
    body.appendChild(el("div", { class: "panel-empty" }, "No workflow defined."));
    return;
  }
  const row = el("div", { class: "flow" });
  stages.forEach((st, i) => {
    if (i) row.appendChild(el("div", { class: "flow-arrow", "aria-hidden": "true" }, "→"));
    const steps = st.steps || (st.step ? [st.step] : []);
    const parallel = steps.length > 1;
    row.appendChild(el("div", { class: "flow-stage" + (parallel ? " flow-parallel" : "") },
      el("div", { class: "flow-stage-head" },
        el("span", { class: "flow-num" }, String(i + 1)),
        el("span", { class: "flow-title" }, st.title || "")),
      el("div", { class: "flow-steps" }, ...steps.map((s) => el("div", { class: "flow-step" }, s))),
      parallel ? el("div", { class: "flow-par-tag" }, "in parallel") : null));
  });
  body.appendChild(row);
  body.appendChild(el("div", { class: "flow-caption" },
    o.caption || "Steps within a stage run in parallel; stages flow left → right."));
});
