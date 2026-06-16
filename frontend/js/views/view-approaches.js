// Informational page: the three RCA approach types + a decision-framework summary.
import { el } from "../core/dom.js";
import * as store from "../core/store.js";

const RULES = [
  ["Fixed workflow", "the exact steps are known and fixed — the template is the runbook. Deterministic, reproducible, cheap."],
  ["Agentic flow (LangGraph)", "the steps are known but the path isn't — a bounded set of tools, with the next step chosen from the data."],
  ["CLI super-agent", "you can't enumerate the steps — novel/exploratory problems where the agent writes new analysis on the fly."],
];

export function render(container) {
  container.appendChild(
    el("div", { class: "view-head" },
      el("h1", {}, "About the approaches"),
      el("p", { class: "muted" },
        "Each template uses one of three approaches. You pick a problem first; the templates under it are labelled with their approach."))
  );

  const solutions = store.get("solutions") || [];
  const grid = el("div", { class: "card-grid" });
  solutions.forEach((s) => {
    const available = s.status === "available";
    grid.appendChild(
      el("div", { class: "sol-card" + (available ? "" : " disabled") },
        el("div", { class: "sol-card-head" },
          el("h3", {}, s.name),
          el("span", { class: "badge " + (available ? "badge-ok" : "badge-soon") }, available ? "Available" : "Coming soon")),
        el("p", { class: "sol-desc" }, s.description),
        el("ul", { class: "cap-list" }, ...(s.capabilities || []).map((c) => el("li", {}, c))))
    );
  });
  container.appendChild(grid);

  container.appendChild(el("h2", { class: "section-title", style: "margin-top:24px" }, "Which approach for which scenario"));
  const rules = el("ul", { class: "rule-list" });
  RULES.forEach(([name, desc]) =>
    rules.appendChild(el("li", {}, el("strong", {}, name + ": "), desc)));
  container.appendChild(rules);

  container.appendChild(
    el("pre", { class: "decision-tree" },
`New RCA problem
   |
   |- Steps fully known & fixed? ----------------- yes -> Fixed workflow
   |                                no
   |- Tools known, only the PATH is data-dependent? - yes -> Agentic flow
   |                                no
   |- Must author new analysis / open exploration? -- yes -> CLI super-agent`)
  );

  container.appendChild(
    el("p", { class: "muted small" },
      "Full framework (comparison matrix, examples, escalation model): docs/02-decision-framework.md")
  );
}
