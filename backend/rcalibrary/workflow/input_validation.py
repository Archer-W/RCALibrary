"""Validate + coerce user-supplied template inputs against the template's spec.

Returns a clean dict of typed values, or raises ``InputValidationError`` with a
``{field: message}`` map that the API maps to a 422.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from ..errors import InputValidationError
from .models import InputType, TemplateInput


def validate_inputs(specs: list[TemplateInput], raw: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for spec in specs:
        provided = spec.name in raw and raw[spec.name] not in (None, "")
        if not provided:
            if spec.required and spec.default is None:
                errors[spec.name] = "This field is required."
                continue
            cleaned[spec.name] = spec.default
            continue

        value = raw[spec.name]
        try:
            value = _coerce(spec, value)
        except (ValueError, TypeError):
            errors[spec.name] = f"Expected {spec.type.value}."
            continue

        err = _check_constraints(spec, value)
        if err:
            errors[spec.name] = err
            continue
        cleaned[spec.name] = value

    if errors:
        raise InputValidationError(errors)
    return cleaned


def _coerce(spec: TemplateInput, value: Any) -> Any:
    t = spec.type
    if t == InputType.string:
        return str(value)
    if t == InputType.int:
        return int(value)
    if t == InputType.float:
        return float(value)
    if t == InputType.bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if t == InputType.enum:
        allowed = {o.value for o in (spec.options or [])}
        sval = str(value)
        if sval not in allowed:
            raise ValueError("not an allowed option")
        return sval
    if t == InputType.date:
        return date.fromisoformat(str(value)).isoformat()
    if t == InputType.datetime:
        return datetime.fromisoformat(str(value)).isoformat()
    return value


def _check_constraints(spec: TemplateInput, value: Any) -> str | None:
    v = spec.validation
    if v is None:
        return None
    if spec.type in (InputType.int, InputType.float):
        if v.min is not None and value < v.min:
            return f"Must be ≥ {v.min}."
        if v.max is not None and value > v.max:
            return f"Must be ≤ {v.max}."
    if spec.type == InputType.string:
        if v.min_length is not None and len(value) < v.min_length:
            return f"Must be at least {v.min_length} characters."
        if v.max_length is not None and len(value) > v.max_length:
            return f"Must be at most {v.max_length} characters."
        if v.pattern is not None and not re.fullmatch(v.pattern, value):
            return f"Must match pattern {v.pattern}."
    return None
