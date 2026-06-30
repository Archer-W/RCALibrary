// Template runner: dynamic input form -> run -> report. Reached from a problem.
import { el, clear } from "../core/dom.js";
import * as endpoints from "../api/endpoints.js";
import { renderForm } from "../forms/form-renderer.js";
import { renderReport } from "../report/report-view.js";
import { renderPanel } from "../panels/registry.js";
import "../panels/panel-flow.js";  // register the "flow" renderer (for the informational workflow)

export function render(container, params) {
  clear(container);
  let reportInstance = null;

  const backLink = el("a", { class: "back-link", href: "#/problems" }, "← Back");
  const titleEl = el("h1", { class: "runner-title" }, params.templateId);
  container.appendChild(el("div", { class: "view-head" }, backLink, titleEl));

  const formWrap = el("div", { class: "form-wrap card" });
  const reportWrap = el("div", { class: "report-wrap" });
  container.appendChild(formWrap);
  container.appendChild(reportWrap);

  (async () => {
    let detail;
    try {
      detail = await endpoints.getTemplate(params.templateId);
    } catch (e) {
      formWrap.appendChild(errorBanner(e));
      return;
    }
    titleEl.textContent = detail.meta.name;
    // Back to the originating problem when known.
    if (detail.meta.problem && detail.meta.problem.id) {
      backLink.setAttribute("href", `#/problem/${encodeURIComponent(detail.meta.problem.id)}`);
      backLink.textContent = `← ${detail.meta.problem.name}`;
    }
    if (detail.meta.description) {
      formWrap.appendChild(el("p", { class: "muted" }, detail.meta.description));
    }
    // Informational triage workflow, shown ABOVE the inputs (before the user runs).
    const wf = detail.meta.workflow;
    if (wf && wf.stages && wf.stages.length) {
      const wfHost = el("div", { class: "workflow-info" });
      formWrap.appendChild(wfHost);
      renderPanel({ id: "workflow", type: "flow", title: "Triage workflow", options: wf }, wfHost);
    }
    formWrap.appendChild(el("h2", { class: "section-title" }, "Inputs"));
    const formHost = el("div", {});
    formWrap.appendChild(formHost);

    // Run (or re-run, bypassing the saved-report cache) and render the result as a
    // customizable report (add library panels, remove, drag/resize, save).
    async function runAndRender(values, inputGroup, refresh, btn) {
      if (btn) { btn.disabled = true; btn.textContent = "Running…"; }
      clear(reportWrap);
      reportWrap.appendChild(el("div", { class: "loading" }, "Running analysis…"));
      try {
        const result = await endpoints.runTemplate(params.templateId, values, inputGroup, refresh);
        clear(reportWrap);
        if (reportInstance) reportInstance.destroy();
        reportInstance = renderReport(result.report, reportWrap, {
          templateId: params.templateId,
          inputs: values,
          inputGroup,
          library: detail.panel_library || [],
          aiPanels: !!detail.ai_panels,
          fromCache: !!result.from_cache,
          onRefresh: () => runAndRender(values, inputGroup, true, null),
        });
      } catch (e) {
        clear(reportWrap);
        if (e.status === 422 && e.body && e.body.errors) {
          reportWrap.appendChild(
            el("div", { class: "banner banner-warn" },
              "Please fix: " + Object.entries(e.body.errors).map(([k, v]) => `${k}: ${v}`).join("; "))
          );
        } else {
          reportWrap.appendChild(errorBanner(e));
        }
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Run analysis"; }
      }
    }

    renderForm(detail, formHost, (values, ctx) => runAndRender(values, ctx.inputGroup, false, ctx.submitBtn));
  })();

  return { destroy: () => reportInstance && reportInstance.destroy() };
}

function errorBanner(e) {
  return el("div", { class: "banner banner-error" }, `Error${e.status ? ` (${e.status})` : ""}: ${e.message || e}`);
}
