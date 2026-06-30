// Renders a report payload and (when given a templateId in opts) makes it directly
// CUSTOMIZABLE — no edit toggle: every panel always shows its drag handle, remove
// (✕) and width-resize edge, and an "add panel" strip sits between every row. Add
// optional panels from the problem's library (computed on demand), remove (with
// confirm), drag to reorder, snap-resize width. "Save" persists the customized
// report so re-searching the same key reloads it (see backend /save + /run cache).
import { el, clear } from "../core/dom.js";
import { renderPanel } from "../panels/registry.js";
import { plotlyReady } from "../panels/plotly-base.js";
import { renderAnomalyBanner } from "./anomaly-summary.js";
import * as endpoints from "../api/endpoints.js";
import { confirmModal, panelPicker, progressCard, setWidthClass, snapWidth } from "./report-customize.js";
import { aiChatModal } from "./report-ai-chat.js";

const rAF = (fn) => (typeof window.requestAnimationFrame === "function" ? window.requestAnimationFrame(fn) : fn());

export function renderReport(report, container, opts = {}) {
  const ctrl = new ReportController(report, container, opts);
  ctrl.render();
  return ctrl;  // { destroy() }
}

class ReportController {
  constructor(report, container, opts) {
    this.report = report;
    this.container = container;
    this.opts = opts || {};
    this.panels = (report.panels || []).slice();  // panel payloads (mutable order/width)
    this.instances = new Map();  // panel id -> { el, resize, destroy }
    this._dragId = null;
    this._seq = 0;  // uniquifier for added-panel instance ids
    this._raf = null;
    // Resize EVERY Plotly plot currently in the grid (robust for on-demand-added
    // panels, which a stale instance map could miss), coalesced to one per frame.
    this._onResize = () => {
      if (this._raf) return;
      this._raf = rAF(() => {
        this._raf = null;
        if (!this.grid || !plotlyReady() || !window.Plotly.Plots) return;
        this.grid.querySelectorAll(".js-plotly-plot").forEach((p) => {
          try { window.Plotly.Plots.resize(p); } catch { /* ignore */ }
        });
      });
    };
  }

  get customizable() { return !!this.opts.templateId; }

  render() {
    clear(this.container);
    this.container.appendChild(this._header());
    if (this.opts.fromCache) this.container.appendChild(this._savedBanner());
    const banner = el("div", { class: "report-banner" });
    this.container.appendChild(banner);
    renderAnomalyBanner(this.report, banner);
    if (this.report.warnings && this.report.warnings.length) {
      this.container.appendChild(
        el("div", { class: "banner banner-warn" }, "Warnings: " + this.report.warnings.join("; ")));
    }
    this.grid = el("div", { class: "panel-grid" });
    this.container.appendChild(this.grid);
    this._renderGrid();
    window.addEventListener("resize", this._onResize);
    rAF(this._onResize);
  }

  destroy() {
    window.removeEventListener("resize", this._onResize);
    this._purgeInstances();
  }

  _purgeInstances() {
    this.instances.forEach((i) => { try { i && i.destroy && i.destroy(); } catch { /* ignore */ } });
    this.instances.clear();
  }

  // -- header -----------------------------------------------------------------
  _header() {
    const left = [
      el("h2", {}, this.report.title || "Report"),
      this.report.generated_at
        ? el("span", { class: "report-time" }, "Generated " + fmtTime(this.report.generated_at)) : null,
    ];
    if (!this.customizable) return el("div", { class: "report-header" }, ...left);
    this.saveBtn = el("button", { class: "btn btn-primary", type: "button", onClick: () => this._save() }, "Save report");
    return el("div", { class: "report-header" }, ...left,
      el("div", { class: "report-actions" }, this.saveBtn));
  }

  _savedBanner() {
    return el("div", { class: "banner banner-saved" },
      el("span", {}, "Loaded a saved report (no recompute). "),
      el("button", { class: "btn btn-link", type: "button",
        onClick: () => this.opts.onRefresh && this.opts.onRefresh() }, "Re-run fresh"));
  }

  // -- grid -------------------------------------------------------------------
  _renderGrid() {
    this._purgeInstances();  // release Plotly resources of the panels we're about to discard
    clear(this.grid);
    const edit = this.customizable;  // always-on for a customizable report (no toggle)
    this.grid.classList.toggle("editing", edit);
    this.panels.forEach((p, i) => {
      if (edit) this.grid.appendChild(this._addStrip(i));
      if (p.__loading) { this.grid.appendChild(progressCard(p.title)); return; }
      const inst = renderPanel(p, this.grid);  // appends the card to the grid (attached -> correct width)
      this.instances.set(p.id, inst);
      if (edit) this._decorate(inst.el, p);
    });
    if (edit) this.grid.appendChild(this._addStrip(this.panels.length));
    rAF(this._onResize);
  }

  _addStrip(index) {
    // The bottom strip (after the last panel) keeps the full affordance with text;
    // the strips BETWEEN rows are slim — just a "+" on a thin line, no text.
    if (index === this.panels.length) {
      return el("div", { class: "panel-add-strip panel-add-strip-end", title: "Add an RCA panel",
        onClick: () => this._openAdd(index) },
        el("span", { class: "panel-add-plus" }, "＋"), el("span", {}, "Add an RCA panel"));
    }
    return el("div", { class: "panel-add-strip panel-add-strip-thin", title: "Add an RCA panel here",
      onClick: () => this._openAdd(index) }, el("span", { class: "panel-add-plus" }, "＋"));
  }

  // Edit-mode controls on a panel card: drag handle, width-resize edge, remove.
  _decorate(card, payload) {
    card.classList.add("panel-editable");
    const drag = el("span", { class: "panel-drag", draggable: "true", title: "Drag to reorder",
      onDragstart: (e) => {
        this._dragId = payload.id; card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        try { e.dataTransfer.setData("text/plain", payload.id); } catch { /* jsdom */ }
      },
      onDragend: () => { card.classList.remove("dragging"); this._dragId = null; },
    }, "⠿");
    const remove = el("button", { class: "panel-remove", type: "button", title: "Remove panel",
      onClick: () => this._remove(payload.id) }, "✕");
    const head = card.querySelector(".panel-head");
    (head || card).appendChild(el("span", { class: "panel-tools" }, drag, remove));

    // right-edge width resizer (snaps to third/half/full)
    const handle = el("div", { class: "panel-resize", title: "Drag to resize width" });
    card.appendChild(handle);
    this._wireResize(card, handle, payload);

    // the card is a drop target for reorder
    card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drag-over"); });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", (e) => {
      e.preventDefault(); card.classList.remove("drag-over"); this._reorder(this._dragId, payload.id);
    });
  }

  _wireResize(card, handle, payload) {
    let active = false;
    handle.addEventListener("pointerdown", (e) => {
      active = true; e.preventDefault();
      try { handle.setPointerCapture(e.pointerId); } catch { /* jsdom */ }
    });
    handle.addEventListener("pointermove", (e) => {
      if (!active) return;
      const gw = this.grid.getBoundingClientRect().width;
      const w = snapWidth(e.clientX - card.getBoundingClientRect().left, gw);
      if (w !== payload.width) { payload.width = w; setWidthClass(card, w); }
    });
    const end = () => { if (!active) return; active = false; const i = this.instances.get(payload.id); i && i.resize && i.resize(); };
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  }

  // -- mutations --------------------------------------------------------------
  _reorder(fromId, toId) {
    if (!fromId || fromId === toId) return;
    const from = this.panels.findIndex((p) => p.id === fromId);
    const to = this.panels.findIndex((p) => p.id === toId);
    if (from < 0 || to < 0) return;
    const [moved] = this.panels.splice(from, 1);
    // after removal, indices past `from` shift down by one — adjust so a forward
    // drag lands ON the drop target, not one slot past it.
    this.panels.splice(from < to ? to - 1 : to, 0, moved);
    this._renderGrid();
  }

  async _remove(id) {
    if (!(await confirmModal("Remove this panel from the report?"))) return;
    this.panels = this.panels.filter((p) => p.id !== id);
    this._renderGrid();
  }

  async _openAdd(index) {
    const choice = await panelPicker(this.opts.library, this.opts.aiPanels);
    if (!choice) return;
    if (choice === "__ai__") { this._addPanelAI(index); return; }  // open the AI chat
    const meta = (this.opts.library || []).find((l) => l.id === choice) || {};
    const uid = ++this._seq;  // unique per add, so the same library panel can be added twice
    const marker = { __loading: true, id: "__loading_" + choice + "_" + uid, title: meta.title || choice };
    this.panels.splice(index, 0, marker);
    this._renderGrid();
    try {
      const res = await endpoints.addPanel(this.opts.templateId, choice, this.opts.inputs, this.opts.inputGroup);
      const panel = res.panel || {};
      panel.id = String(panel.id || choice) + "::" + uid;  // unique instance id (avoid collisions on re-add)
      this._replaceMarker(marker.id, panel);
    } catch (e) {
      this._replaceMarker(marker.id, {
        __error: true, id: "__err_" + choice + "_" + uid, type: "markdown", width: "full",
        title: (meta.title || "Panel") + " — failed",
        markdown: "Could not load this panel: " + (e && e.message ? e.message : e),
      });
    }
  }

  // Open the AI chat. Each panel the agent builds is inserted at `index` (then
  // subsequent panels stack just after it); the chat stays open for refinement.
  _addPanelAI(index) {
    let insertAt = index;
    const self = this;
    aiChatModal({
      send: (message, sessionId) => endpoints.aiPanelChat(self.opts.templateId, {
        message, session_id: sessionId, inputs: self.opts.inputs, input_group: self.opts.inputGroup,
      }),
      onPanel: (panel) => {
        const uid = ++self._seq;
        panel.id = String(panel.id || "ai") + "::" + uid;  // unique instance id
        self.panels.splice(insertAt, 0, panel);
        insertAt += 1;
        self._renderGrid();
      },
    });
  }

  _replaceMarker(markerId, panel) {
    const i = this.panels.findIndex((p) => p.id === markerId);
    if (i < 0) return;
    this.panels[i] = panel;
    this._renderGrid();
  }

  async _save() {
    if (!this.saveBtn) return;
    // persist real panels only — not in-flight loaders or failure placeholders
    const report = { ...this.report, panels: this.panels.filter((p) => !p.__loading && !p.__error) };
    this.saveBtn.disabled = true;
    this.saveBtn.textContent = "Saving…";
    try {
      await endpoints.saveReport(this.opts.templateId, this.opts.inputs, this.opts.inputGroup, report);
      this.saveBtn.textContent = "Saved ✓";
      setTimeout(() => { this.saveBtn.textContent = "Save"; this.saveBtn.disabled = false; }, 1600);
    } catch {
      this.saveBtn.textContent = "Save failed";
      setTimeout(() => { this.saveBtn.textContent = "Save"; this.saveBtn.disabled = false; }, 1600);
    }
  }
}

function fmtTime(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
