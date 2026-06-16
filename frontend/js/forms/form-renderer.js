// Builds a form from a template's input schema and collects typed values.
import { el, mount } from "../core/dom.js";
import { createField } from "./form-fields.js";
import { validateField } from "./form-validate.js";

export function renderForm(schema, container, onSubmit) {
  const fields = (schema.inputs || []).map(createField);
  const form = el("form", { class: "rca-form" });

  fields.forEach((f) => {
    form.appendChild(f.wrapper);
    f.input.addEventListener("blur", () => f.setError(validateField(f.spec, f.read())));
  });

  const submitBtn = el("button", { type: "submit", class: "btn btn-primary" }, "Run analysis");
  form.appendChild(el("div", { class: "form-actions" }, submitBtn));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const values = {};
    let ok = true;
    fields.forEach((f) => {
      const val = f.read();
      values[f.spec.name] = val;
      const err = validateField(f.spec, val);
      f.setError(err);
      if (err) ok = false;
    });
    if (ok) onSubmit(values, { submitBtn });
  });

  mount(container, form);
  return {
    getValues: () => Object.fromEntries(fields.map((f) => [f.spec.name, f.read()])),
    submitBtn,
  };
}
