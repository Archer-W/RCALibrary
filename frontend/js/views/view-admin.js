// Admin & usage-log placeholder (access management + usage logging are deferred).
import { el } from "../core/dom.js";

export function renderAdmin(container) {
  container.appendChild(
    el("div", { class: "placeholder-card card" },
      el("span", { class: "badge badge-soon" }, "Coming soon"),
      el("h1", {}, "Admin & Usage"),
      el("p", { class: "muted" },
        "Access management and usage logging are deferred in this build. The seams " +
        "exist in the backend (auth + audit interfaces); this is where the usage log will render."),
      el("table", { class: "admin-table" },
        el("thead", {}, el("tr", {},
          el("th", {}, "User"), el("th", {}, "Template"), el("th", {}, "Timestamp"), el("th", {}, "Status"))),
        el("tbody", {}, el("tr", {}, el("td", { colspan: "4" },
          el("div", { class: "admin-empty" }, "No usage records yet."))))))
  );
}
