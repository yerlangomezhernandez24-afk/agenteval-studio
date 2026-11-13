"""Independent contract checks. Missing/ill-typed fields are not exact-match failures."""

from typing import Any
from unicodedata import normalize

from pydantic import ValidationError

from agenteval.io import parse_json
from agenteval.models import Case, Check, Criterion, LegacyResponse, Outcome, Response


def check(criterion: Criterion, outcome: Outcome, reason: str) -> Check:
    return Check(criterion=criterion, outcome=outcome, reason=reason)


def evaluate(case: Case, raw: str, criteria_version: str = "1.1") -> list[Check]:
    if criteria_version not in {"1.0", "1.1"}:
        raise ValueError("Unsupported criteria version")
    checks: list[Check] = []
    obj: Any = None
    parsed = False
    try:
        obj = parse_json(raw)
        parsed = True
        checks.append(check("json_valid", "pass", "Strict JSON parsed"))
    except (ValueError, RecursionError):
        checks.append(check("json_valid", "fail", "Invalid JSON, duplicate keys or nesting"))
    if parsed:
        try:
            response_model = LegacyResponse if criteria_version == "1.0" else Response
            response_model.model_validate(obj)
            checks.append(check("schema_valid", "pass", "Strict response schema satisfied"))
        except ValidationError:
            checks.append(check("schema_valid", "fail", "Required fields, types, enums or extras"))
    else:
        checks.append(check("schema_valid", "not_evaluable", "JSON parsing failed"))
    fields: list[tuple[Criterion, str]] = [
        ("category", "category"),
        ("priority", "priority"),
        ("escalation", "requires_human"),
    ]
    for criterion, field in fields:
        expected = getattr(case.expected, field)
        if not isinstance(obj, dict) or field not in obj or type(obj[field]) is not type(expected):
            checks.append(check(criterion, "not_evaluable", "Field missing or wrong type"))
        else:
            outcome: Outcome = "pass" if obj[field] == expected else "fail"
            checks.append(check(criterion, outcome, "Exact match against synthetic label"))
    if not case.contains and not case.excludes:
        checks.append(check("content", "not_evaluable", "No text restrictions for this case"))
    elif criteria_version == "1.0":
        folded = raw.casefold()
        valid = all(term.casefold() in folded for term in case.contains) and all(
            term.casefold() not in folded for term in case.excludes
        )
        checks.append(check("content", "pass" if valid else "fail", "Literal casefold substring"))
    elif not isinstance(obj, dict) or not isinstance(obj.get("summary"), str):
        checks.append(check("content", "not_evaluable", "Decoded summary missing or not a string"))
    else:

        def canonical(text: str) -> str:
            return normalize("NFC", normalize("NFC", text).casefold())

        folded = canonical(obj["summary"])
        valid = all(canonical(term) in folded for term in case.contains) and all(
            canonical(term) not in folded for term in case.excludes
        )
        checks.append(check("content", "pass" if valid else "fail", "Decoded summary NFC casefold"))
    return checks
