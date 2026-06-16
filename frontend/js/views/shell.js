// Persistent chrome: header (with placeholder user indicator) + sidebar nav.
// Problem-first: the sidebar is Problems / About approaches / Admin.
import { el, clear } from "../core/dom.js";

const NAV = [
  { route: "#/problems", label: "Problems", match: ["#/problems", "#/problem", "#/run"] },
  { route: "#/approaches", label: "About approaches", match: ["#/approaches"] },
];

export function renderShell(root) {
  clear(root);

  const header = el(
    "header",
    { class: "app-header" },
    el("a", { class: "brand", href: "#/problems" },
      el("span", { class: "brand-mark" }), "RCA", el("span", { class: "brand-accent" }, "Library")),
    el("div", { class: "header-spacer" }),
    el("a", { class: "header-link", href: "#/admin", title: "Admin & Usage" }, "⚙"),
    el("div", { class: "user-indicator" }, "◐ Sign in")
  );

  const sidebar = el("nav", { class: "sidebar", id: "sidebar" });
  const main = el("main", { class: "main", id: "main" });

  root.appendChild(header);
  root.appendChild(el("div", { class: "app-layout" }, sidebar, main));

  const isActive = (matches) => matches.some((m) => location.hash.startsWith(m)) ||
    (matches.includes("#/problems") && (location.hash === "" || location.hash === "#/"));

  const renderSidebar = () => {
    clear(sidebar);
    sidebar.appendChild(el("div", { class: "sidebar-title" }, "Navigate"));
    NAV.forEach((item) =>
      sidebar.appendChild(
        el("a", { class: "nav-item" + (isActive(item.match) ? " active" : ""), href: item.route },
          el("span", { class: "nav-label" }, item.label))
      )
    );
    sidebar.appendChild(el("div", { class: "sidebar-spacer" }));
    sidebar.appendChild(
      el("a", { class: "nav-item" + (location.hash.startsWith("#/admin") ? " active" : ""), href: "#/admin" },
        el("span", { class: "nav-label" }, "Admin / Usage"),
        el("span", { class: "badge badge-soon" }, "soon"))
    );
  };

  window.addEventListener("hashchange", renderSidebar);
  renderSidebar();

  return main;
}
