"""
Shared requirement-construction logic used by every intake path - the
strict Excel template parser (excel_parser.py) and the Groq-based
free-layout extractor (app/services/extraction_service.py) - so raw
top-level/section values, however they were extracted, are always
validated the same way with the same fail-soft "one bad section never
blocks the rest" behavior, and the same synonym/type coercion rules.
Keeping this in one place is what lets both intake paths share a single
source of truth instead of drifting apart.
"""
from datetime import datetime, timezone

from pydantic import ValidationError

from app.domain.enums import Severity
from app.domain.intake import ParseIssue
from app.domain.requirements import (
    AvailabilityRequirement,
    BusinessContext,
    ComputeRequirement,
    CustomerRequirement,
    DatabaseRequirement,
    KubernetesRequirement,
    NetworkRequirement,
    StorageRequirement,
)
from app.intake.schema import SECTION_KEYS

SECTION_MODELS = {
    "compute": ComputeRequirement,
    "storage": StorageRequirement,
    "database": DatabaseRequirement,
    "network": NetworkRequirement,
    "kubernetes": KubernetesRequirement,
    "availability": AvailabilityRequirement,
    "business": BusinessContext,
}
_SECTION_DISPLAY_LABELS = {key: label for label, key in SECTION_KEYS.items()}

_TRUE_STRINGS = {"true", "yes", "y", "1"}
_FALSE_STRINGS = {"false", "no", "n", "0"}


def coerce_value(raw_value: object, spec) -> object:
    """Interprets one raw cell/JSON value according to a FIELD_SCHEMA
    FieldSpec's declared type - shared by the Excel template parser and the
    Groq extractor so "TRUE"/true/1, "4"/4, and enum values with mismatched
    case are all interpreted identically regardless of which intake path
    produced them. Raises (TypeError, ValueError) on anything it can't
    confidently interpret - callers turn that into a per-field warning."""
    if spec.value_type == "str":
        return str(raw_value).strip()

    if spec.value_type == "int":
        if isinstance(raw_value, bool):
            raise ValueError("boolean given for an integer field")
        return int(float(raw_value)) if isinstance(raw_value, str) else int(raw_value)

    if spec.value_type == "float":
        if isinstance(raw_value, bool):
            raise ValueError("boolean given for a float field")
        return float(raw_value)

    if spec.value_type == "bool":
        if isinstance(raw_value, bool):
            return raw_value
        text = str(raw_value).strip().lower()
        if text in _TRUE_STRINGS:
            return True
        if text in _FALSE_STRINGS:
            return False
        raise ValueError(f"'{raw_value}' is not a recognized boolean")

    if spec.value_type == "enum":
        text = str(raw_value).strip()
        for choice in spec.choices or []:
            if choice.lower() == text.lower():
                return choice
        raise ValueError(f"'{raw_value}' is not one of {spec.choices}")

    raise ValueError(f"Unknown field type '{spec.value_type}'")


def build_customer_requirement(
    top_level: dict, sections: dict[str, dict],
) -> tuple[CustomerRequirement | None, list[ParseIssue]]:
    """`top_level` holds CustomerRequirement's own fields (project_name,
    region, ...); `sections` maps a SECTION_MODELS key (e.g. "compute") to
    that section's raw field values. A missing/empty section is left out of
    the result entirely (None) rather than defaulted - only a section the
    customer (or the extractor, on their behalf) actually provided data for
    is ever priced."""
    issues: list[ParseIssue] = []
    top_level = dict(top_level)

    if not str(top_level.get("project_name") or "").strip():
        default_name = f"Quick Estimate {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
        top_level["project_name"] = default_name
        issues.append(ParseIssue(
            field="Project Name",
            message=f"Project Name was left blank - used '{default_name}' so this could still be parsed and priced. Rename it later when you save it to a project.",
            severity=Severity.WARNING,
        ))

    built_sections: dict = {}
    for section_key, model_cls in SECTION_MODELS.items():
        values = sections.get(section_key) or {}
        if not values:
            built_sections[section_key] = None
            continue
        try:
            built_sections[section_key] = model_cls(**values)
        except ValidationError as exc:
            section_label = _SECTION_DISPLAY_LABELS.get(section_key, section_key)
            for err in exc.errors():
                field_name = ".".join(str(p) for p in err["loc"]) or section_key
                issues.append(ParseIssue(
                    field=f"{section_label}.{field_name}",
                    message=f"{err['msg']} - the entire {section_label} section was skipped.",
                    severity=Severity.BLOCKER,
                ))
            built_sections[section_key] = None

    try:
        requirement = CustomerRequirement(**top_level, **built_sections)
    except ValidationError as exc:
        for err in exc.errors():
            issues.append(ParseIssue(
                field=".".join(str(p) for p in err["loc"]), message=err["msg"], severity=Severity.BLOCKER,
            ))
        return None, issues

    return requirement, issues


def has_any_section(sections: dict[str, dict | None]) -> bool:
    """True if at least one section dict has any field set - used to decide
    whether a parse actually recovered real customer data, vs. an
    unrecognized layout that only ever produces the auto-generated project
    name (see build_customer_requirement above)."""
    return any(sections.get(key) for key in SECTION_MODELS)
