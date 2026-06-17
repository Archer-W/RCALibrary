// One control factory per input type. Each returns { wrapper, input, read, setError, spec }.
import { el } from "../core/dom.js";
import { mdInline } from "../core/format.js";

const HTML_TYPE = {
  int: "number",
  float: "number",
  date: "date",
  datetime: "datetime-local",
  string: "text",
};

export function createField(spec, idPrefix = "") {
  // idPrefix keeps ids unique when the same field name appears in multiple
  // input groups (all groups live in the DOM at once, just hidden).
  const id = `f_${idPrefix}${spec.name}`;
  let input;

  if (spec.type === "enum") {
    input = el(
      "select",
      { id, class: "control" },
      ...(spec.options || []).map((o) => el("option", { value: o.value }, o.label))
    );
    if (spec.default != null) input.value = spec.default;
  } else if (spec.type === "bool") {
    input = el("input", { id, type: "checkbox", class: "control-check" });
    if (spec.default) input.checked = true;
  } else {
    input = el("input", { id, type: HTML_TYPE[spec.type] || "text", class: "control" });
    if (spec.type === "int") input.step = "1";
    if (spec.type === "float") input.step = "any";
    if (spec.placeholder) input.placeholder = spec.placeholder;
    const v = spec.validation || {};
    if (v.min != null) input.min = v.min;
    if (v.max != null) input.max = v.max;
    if (spec.default != null) input.value = spec.default;
  }

  const errorEl = el("div", { class: "field-error" });
  const help = spec.help ? el("div", { class: "field-help", html: mdInline(spec.help) }) : null;
  const req = spec.required ? el("span", { class: "req" }, " *") : null;

  let wrapper;
  if (spec.type === "bool") {
    // checkbox inline with its label, help below
    wrapper = el(
      "div",
      { class: "field field-check" },
      el("label", { class: "check-row" }, input, el("span", {}, spec.label, req)),
      help,
      errorEl
    );
  } else {
    wrapper = el(
      "div",
      { class: "field" },
      el("label", { for: id, class: "field-label" }, spec.label, req),
      input,
      help,
      errorEl
    );
  }

  function read() {
    if (spec.type === "bool") return input.checked;
    const raw = input.value;
    if (raw === "") return spec.default != null ? spec.default : "";
    if (spec.type === "int") return parseInt(raw, 10);
    if (spec.type === "float") return parseFloat(raw);
    return raw;
  }

  function setError(msg) {
    errorEl.textContent = msg || "";
    input.classList.toggle("invalid", !!msg);
  }

  return { wrapper, input, read, setError, spec };
}
