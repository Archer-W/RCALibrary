// Builds a form from a template's input schema and collects typed values.
// Supports a flat `inputs` list OR `input_groups` (mutually-exclusive sets the
// user chooses between; only the active set is submitted, with its group key).
import { el, mount } from "../core/dom.js";
import { createField, mdInline } from "./form-fields.js";
import { validateField } from "./form-validate.js";

// Unique radio-group name per rendered form (radios group by name document-wide).
let _groupSeq = 0;

export function renderForm(schema, container, onSubmit) {
  if (schema.input_groups && schema.input_groups.length) {
    return renderGroupedForm(schema.input_groups, container, onSubmit);
  }
  return renderFlatForm(schema.inputs || [], container, onSubmit);
}

function submitButton() {
  return el("button", { type: "submit", class: "btn btn-primary" }, "Run analysis");
}

function collect(fields) {
  const values = {};
  let ok = true;
  fields.forEach((f) => {
    const v = f.read();
    values[f.spec.name] = v;
    const err = validateField(f.spec, v);
    f.setError(err);
    if (err) ok = false;
  });
  return { values, ok };
}

function renderFlatForm(inputSpecs, container, onSubmit) {
  const fields = inputSpecs.map((s) => createField(s));
  const form = el("form", { class: "rca-form" });
  fields.forEach((f) => {
    form.appendChild(f.wrapper);
    f.input.addEventListener("blur", () => f.setError(validateField(f.spec, f.read())));
  });
  const submitBtn = submitButton();
  form.appendChild(el("div", { class: "form-actions" }, submitBtn));
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const { values, ok } = collect(fields);
    if (ok) onSubmit(values, { submitBtn, inputGroup: null });
  });
  mount(container, form);
  return { submitBtn };
}

function renderGroupedForm(groups, container, onSubmit) {
  const form = el("form", { class: "rca-form" });
  form.appendChild(el("div", { class: "section-title" }, "Look up by"));

  const groupName = `rca_group_${++_groupSeq}`;
  let activeKey = groups[0].key;
  const sections = [];

  groups.forEach((g, i) => {
    const fields = g.inputs.map((s) => createField(s, `${g.key}_`));
    fields.forEach((f) =>
      f.input.addEventListener("blur", () => f.setError(validateField(f.spec, f.read())))
    );
    const radio = el("input", { type: "radio", name: groupName, value: g.key });
    if (i === 0) radio.checked = true;
    const fieldsWrap = el("div", { class: "group-fields" }, ...fields.map((f) => f.wrapper));
    const help = g.help ? el("div", { class: "field-help", html: mdInline(g.help) }) : null;

    form.appendChild(
      el("div", { class: "input-group" },
        el("label", { class: "group-head" }, radio, el("span", { class: "group-label" }, g.label)),
        help,
        fieldsWrap)
    );

    radio.addEventListener("change", () => {
      if (radio.checked) {
        activeKey = g.key;
        refresh();
      }
    });
    sections.push({ key: g.key, fields, fieldsWrap });
  });

  function refresh() {
    sections.forEach((s) => {
      s.fieldsWrap.style.display = s.key === activeKey ? "" : "none";
    });
  }
  refresh();

  const submitBtn = submitButton();
  form.appendChild(el("div", { class: "form-actions" }, submitBtn));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const active = sections.find((s) => s.key === activeKey);
    const { values, ok } = collect(active.fields);
    if (ok) onSubmit(values, { submitBtn, inputGroup: activeKey });
  });

  mount(container, form);
  return { submitBtn };
}
