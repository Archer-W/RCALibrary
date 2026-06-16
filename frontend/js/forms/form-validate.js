// Client-side input validation (mirrors the backend's rules for fast feedback).

export function validateField(spec, value) {
  const empty = value === undefined || value === null || value === "";
  if (empty) {
    const hasDefault = spec.default !== null && spec.default !== undefined;
    if (spec.required && !hasDefault) return "This field is required.";
    return null;
  }
  const v = spec.validation || {};

  if (spec.type === "int" || spec.type === "float") {
    const num = Number(value);
    if (Number.isNaN(num)) return "Must be a number.";
    if (spec.type === "int" && !Number.isInteger(num)) return "Must be a whole number.";
    if (v.min != null && num < v.min) return `Must be ≥ ${v.min}.`;
    if (v.max != null && num > v.max) return `Must be ≤ ${v.max}.`;
  }

  if (spec.type === "string") {
    const s = String(value);
    if (v.min_length != null && s.length < v.min_length) return `Must be at least ${v.min_length} characters.`;
    if (v.max_length != null && s.length > v.max_length) return `Must be at most ${v.max_length} characters.`;
    if (v.pattern) {
      let ok = true;
      try { ok = new RegExp(`^(?:${v.pattern})$`).test(s); } catch { ok = true; }
      if (!ok) return "Invalid format.";
    }
  }

  if (spec.type === "enum") {
    const allowed = (spec.options || []).map((o) => o.value);
    if (!allowed.includes(String(value))) return "Not an allowed option.";
  }
  return null;
}

export function validateAll(specs, values) {
  const errors = {};
  for (const spec of specs) {
    const err = validateField(spec, values[spec.name]);
    if (err) errors[spec.name] = err;
  }
  return errors;
}
