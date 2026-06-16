// Template runner: dynamic input form -> run -> report. Reached from a problem.
import { el, clear } from "../core/dom.js";
import * as endpoints from "../api/endpoints.js";
import { renderForm } from "../forms/form-renderer.js";
import { renderReport } from "../report/report-view.js";

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
    formWrap.appendChild(el("h2", { class: "section-title" }, "Inputs"));
    const formHost = el("div", {});
    formWrap.appendChild(formHost);

    renderForm(detail, formHost, async (values, ctx) => {
      ctx.submitBtn.disabled = true;
      ctx.submitBtn.textContent = "Running…";
      clear(reportWrap);
      reportWrap.appendChild(el("div", { class: "loading" }, "Running analysis…"));
      try {
        const result = await endpoints.runTemplate(params.templateId, values, ctx.inputGroup);
        clear(reportWrap);
        if (reportInstance) reportInstance.destroy();
        reportInstance = renderReport(result.report, reportWrap);
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
        ctx.submitBtn.disabled = false;
        ctx.submitBtn.textContent = "Run analysis";
      }
    });
  })();

  return { destroy: () => reportInstance && reportInstance.destroy() };
}

function errorBanner(e) {
  return el("div", { class: "banner banner-error" }, `Error${e.status ? ` (${e.status})` : ""}: ${e.message || e}`);
}
