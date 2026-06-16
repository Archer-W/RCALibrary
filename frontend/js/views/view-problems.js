// Problem-first navigation: a catalog of RCA problems, then the templates
// available for a chosen problem (each annotated with its approach type).
import { el } from "../core/dom.js";
import * as endpoints from "../api/endpoints.js";

export async function render(container, params) {
  if (params.problemId) {
    return renderProblemDetail(container, params.problemId);
  }
  return renderCatalog(container);
}

async function renderCatalog(container) {
  container.appendChild(
    el("div", { class: "view-head" },
      el("h1", {}, "What problem are you solving?"),
      el("p", { class: "muted" }, "Pick a problem to see the templates available for it."))
  );
  const grid = el("div", { class: "card-grid" });
  container.appendChild(grid);

  let problems;
  try {
    problems = await endpoints.listProblems();
  } catch (e) {
    grid.appendChild(errorBanner(e));
    return;
  }
  if (!problems.length) {
    grid.appendChild(el("p", { class: "muted" }, "No problems available yet."));
    return;
  }
  problems.forEach((p) => {
    const tags = (p.tags || []).length
      ? el("div", { class: "problem-tags" }, ...p.tags.map((t) => el("span", { class: "tag" }, t)))
      : null;

    const templateBadges = (p.templates || []).length
      ? (p.templates || []).map((t) => {
          const available = t.status === "available";
          return el(
            "span",
            {
              class: "badge badge-approach" + (available ? "" : " badge-muted"),
              title: t.name + (available ? "" : " (coming soon)"),
            },
            t.approach_name
          );
        })
      : [el("span", { class: "muted small" }, "none yet")];

    grid.appendChild(
      el("a", { class: "problem-card", href: `#/problem/${encodeURIComponent(p.id)}` },
        el("div", { class: "problem-card-head" },
          el("h3", {}, p.name),
          p.domain ? el("span", { class: "badge badge-domain" }, p.domain) : null),
        tags,
        el("p", { class: "sol-desc" }, p.description),
        el("div", { class: "problem-templates" },
          el("span", { class: "problem-templates-label" }, "Templates:"),
          ...templateBadges))
    );
  });
}

async function renderProblemDetail(container, problemId) {
  const head = el("div", { class: "view-head" },
    el("a", { class: "back-link", href: "#/problems" }, "← Problems"),
    el("h1", { class: "problem-title" }, problemId));
  container.appendChild(head);
  const grid = el("div", { class: "card-grid" });
  container.appendChild(grid);

  let problems;
  try {
    problems = await endpoints.listProblems();
  } catch (e) {
    grid.appendChild(errorBanner(e));
    return;
  }
  const problem = problems.find((p) => p.id === problemId);
  if (!problem) {
    grid.appendChild(el("p", { class: "muted" }, "Problem not found."));
    return;
  }
  head.querySelector(".problem-title").textContent = problem.name;
  if (problem.description) {
    head.appendChild(el("p", { class: "muted" }, problem.description));
  }

  problem.templates.forEach((t) => {
    const available = t.status === "available";
    const card = el(
      available ? "a" : "div",
      {
        class: "tmpl-card" + (available ? "" : " disabled"),
        href: available ? `#/run/${encodeURIComponent(t.id)}` : null,
      },
      el("div", { class: "tmpl-card-head" },
        el("span", { class: "badge badge-approach" }, t.approach_name),
        el("span", { class: "badge " + (available ? "badge-ok" : "badge-soon") },
          available ? "Available" : "Coming soon")),
      el("h3", {}, t.name),
      el("p", { class: "tmpl-desc" }, t.description),
      el("div", { class: "tmpl-tags" }, ...(t.tags || []).map((tag) => el("span", { class: "tag" }, tag)))
    );
    grid.appendChild(card);
  });
}

function errorBanner(e) {
  return el("div", { class: "banner banner-error" }, `Error${e.status ? ` (${e.status})` : ""}: ${e.message || e}`);
}
