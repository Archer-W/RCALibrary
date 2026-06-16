// One control factory per input type. Each returns { wrapper, input, read, setError, spec }.
import { el } from "../core/dom.js";

const HTML_TYPE = {
  int: "number",
  float: "number",
  date: "date",
  datetime: "datetime-local",
  string: "text",
};

export function createField(spec) {
  const id = `f_${spec.name}`;
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
    const v = spec.validation || {};
    if (v.min != null) input.min = v.min;
    if (v.max != null) input.max = v.max;
    if (spec.default != null) input.value = spec.default;
  }

  const errorEl = el("div", { class: "field-error" });
  const wrapper = el(
    "div",
    { class: "field" },
    el(
      "label",
      { for: id, class: "field-label" },
      spec.label,
      spec.required ? el("span", { class: "req" }, " *") : null
    ),
    input,
    spec.help ? el("div", { class: "field-help" }, spec.help) : null,
    errorEl
  );

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
