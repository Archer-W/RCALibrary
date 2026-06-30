// Reusable UI bits for report customization: a loading-panel placeholder, a
// confirm modal, the "add panel" picker, and grid-width snapping. The orchestration
// (add/remove/reorder/resize/save) lives in report-view.js (ReportController).
import { el } from "../core/dom.js";

export const WIDTHS = ["third", "half", "full"];
const WIDTH_FRAC = { third: 1 / 3, half: 1 / 2, full: 1 };

export function setWidthClass(card, width) {
  card.classList.remove("panel-third", "panel-half", "panel-full");
  card.classList.add("panel-" + width);
}

// Snap a dragged pixel width to the nearest grid span name (third/half/full).
export function snapWidth(px, containerPx) {
  const frac = containerPx > 0 ? px / containerPx : 1;
  let best = "full", bestD = Infinity;
  for (const w of WIDTHS) {
    const d = Math.abs(frac - WIDTH_FRAC[w]);
    if (d < bestD) { bestD = d; best = w; }
  }
  return best;
}

// An indeterminate "loading panel" placeholder shown while a library panel computes.
export function progressCard(title) {
  return el("div", { class: "panel panel-full panel-loading" },
    el("div", { class: "panel-head" }, el("h3", { class: "panel-title" }, "Loading: " + (title || "panel"))),
    el("div", { class: "panel-body" },
      el("div", { class: "panel-progress" }, el("div", { class: "panel-progress-bar" })),
      el("div", { class: "panel-progress-label" }, "Computing on demand…")));
}

// Confirm dialog -> Promise<boolean>.
export function confirmModal(message, { confirmLabel = "Remove", danger = true } = {}) {
  return new Promise((resolve) => {
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    const close = (val) => { overlay.remove(); document.removeEventListener("keydown", onKey); resolve(val); };
    const overlay = el("div",
      { class: "modal-overlay", onClick: (e) => { if (e.target === overlay) close(false); } },
      el("div", { class: "modal", role: "dialog" },
        el("div", { class: "modal-msg" }, message),
        el("div", { class: "modal-actions" },
          el("button", { class: "btn btn-ghost", type: "button", onClick: () => close(false) }, "Cancel"),
          el("button", { class: "btn " + (danger ? "btn-danger" : "btn-primary"), type: "button",
            onClick: () => close(true) }, confirmLabel))));
    document.body.appendChild(overlay);
    document.addEventListener("keydown", onKey);
  });
}

// "Add a panel" picker -> Promise<panelId | "__ai__" | null>. Lists the problem's
// library panels + an AI option (disabled unless aiPanels is on — reserved).
export function panelPicker(library, aiPanels) {
  return new Promise((resolve) => {
    const onKey = (e) => { if (e.key === "Escape") close(null); };
    const close = (val) => { overlay.remove(); document.removeEventListener("keydown", onKey); resolve(val); };
    // AI-only panels (requires_ai) are not addable manually — they need NL input
    // and are offered through the AI chat instead.
    const items = (library || []).filter((p) => !p.requires_ai).map((p) =>
      el("button", { class: "picker-item", type: "button", onClick: () => close(p.id) },
        el("div", { class: "picker-item-title" }, p.title),
        p.description ? el("div", { class: "picker-item-desc" }, p.description) : null,
        el("span", { class: "picker-item-type" }, p.type)));
    const aiItem = el("button",
      {
        class: "picker-item picker-item-ai" + (aiPanels ? "" : " is-disabled"),
        type: "button", disabled: !aiPanels,
        title: aiPanels ? "" : "Coming soon — fixed + agentic template",
        onClick: aiPanels ? () => close("__ai__") : null,
      },
      el("div", { class: "picker-item-title" }, "✨ Ask AI to build a panel"),
      el("div", { class: "picker-item-desc" }, aiPanels ? "Describe the data you want." : "Coming soon"));
    const overlay = el("div",
      { class: "modal-overlay", onClick: (e) => { if (e.target === overlay) close(null); } },
      el("div", { class: "picker", role: "dialog" },
        el("div", { class: "picker-head" }, "Add an RCA panel"),
        el("div", { class: "picker-list" },
          ...(items.length ? items : [el("div", { class: "picker-empty" }, "No optional panels for this problem.")]),
          aiItem)));
    document.body.appendChild(overlay);
    document.addEventListener("keydown", onKey);
  });
}
