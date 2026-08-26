"""
ExtractionService: turns an arbitrary customer requirements workbook - any
sheet names, headers, or layout, not just this platform's own questionnaire
template - into a CustomerRequirement via Groq.

Only used as a fallback: app/intake/excel_parser.py (the strict template
parser) is always tried first and wins whenever it recognizes anything,
since it needs no LLM call at all. This service only runs when that parser
found zero recognizable fields - i.e. the workbook clearly isn't in the
platform's own layout.

Hard invariant, identical in spirit to ExplanationService
(app/services/explanation_service.py): Groq only ever extracts/labels
values that are already present in the customer's own file. It is never
asked for, and structurally cannot produce - CustomerRequirement has no
such fields - a price, a SKU, or a currency figure; pricing is done
entirely afterwards by the deterministic PricingEngine, exactly like every
other intake path. Every value Groq returns is re-validated through the
exact same Pydantic models and coercion rules (app/intake/build.py) the
strict template parser uses, so a hallucinated or out-of-range value is
caught and reported per-field/per-section, never trusted outright.
Anything Groq isn't confident about must come back as an `unmapped` item,
surfaced to the user as a review warning instead of being guessed.

If Groq is unavailable, times out, rate-limits, or returns something that
can't be parsed as the expected JSON shape, extraction fails cleanly
(requirement=None, one clear ParseIssue) - it never raises, and the
deterministic pricing pipeline is simply never invoked for this upload.
"""
from __future__ import annotations

import json
import logging

from app.domain.assumption import Assumption
from app.domain.enums import Severity
from app.domain.intake import ParseIssue
from app.domain.requirements import CustomerRequirement
from app.intake.build import build_customer_requirement, coerce_value, has_any_section
from app.intake.excel_parser import ExcelQuestionnaireParser
from app.intake.schema import FIELD_SCHEMA
from app.intake.workbook_reader import dump_workbook_text
from app.llm.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

UNMAPPABLE_MESSAGE = (
    "We could not confidently identify the required cloud resources from this workbook. "
    "Please review the extracted requirements below, correct or add anything that's missing, "
    "or download the standard template and fill it in directly."
)

_SPEC_BY_SECTION_FIELD = {spec.path: spec for spec in FIELD_SCHEMA if len(spec.path) == 2}
_REGION_SPEC = next(spec for spec in FIELD_SCHEMA if spec.path == ("region",))

_SYSTEM_PROMPT = """\
You extract Google Cloud infrastructure requirements from a raw dump of an \
arbitrary customer Excel workbook - the sheet names, headers, and layout \
are unknown and may not match any standard template. You are given the \
full text of every sheet, row by row, cells separated by " | ".

Extract ONLY values that are explicitly present in the source text. Never \
invent, guess, estimate, or fabricate a plausible-looking number that isn't \
actually there. Never calculate, select, or state a price, cost, or SKU - \
pricing is handled entirely afterwards by a separate deterministic engine \
that you have no part in and must never influence.

Recognize common synonyms for the same concept - use judgment for other \
reasonable synonyms too, but only when you are actually confident:
- "CPU" / "vCPU" / "Processors" / "Cores" -> compute.vcpu (or database.vcpu under a database/DB section)
- "RAM" / "Memory" / "Memory GB" -> compute.ram_gb (or database.ram_gb under a database section)
- "Disk" / "Storage" / "Volume" -> storage.size_gb
- "DB" / "Database" / "Cloud SQL" -> a database section (set database.required = true)

Respond with ONLY a single JSON object, no markdown formatting, no code \
fences, matching exactly this shape (use null for anything not present; \
omit a whole section object, i.e. set it to null, if the source has no \
data for it at all):
{
  "project_name": "<string or null>",
  "region_hint": "<a GCP region string such as us-central1 ONLY if explicitly stated, else null>",
  "compute": {"machine_family": str|null, "vcpu": number|null, "ram_gb": number|null, "instance_count": number|null, "gpu_type": str|null, "gpu_count": number|null} | null,
  "storage": {"disk_type": str|null, "size_gb": number|null, "snapshot_enabled": bool|null, "snapshot_retention_days": number|null} | null,
  "database": {"required": bool|null, "engine": str|null, "size_gb": number|null, "vcpu": number|null, "ram_gb": number|null, "high_availability": bool|null} | null,
  "network": {"load_balancer_required": bool|null, "external_ip_count": number|null, "estimated_egress_gb_per_month": number|null, "estimated_ingress_gb_per_month": number|null, "cdn_enabled": bool|null, "vpn_required": bool|null} | null,
  "kubernetes": {"required": bool|null, "node_count": number|null, "autopilot": bool|null} | null,
  "availability": {"high_availability": bool|null, "target_uptime_percent": number|null, "backup_frequency": str|null, "disaster_recovery_required": bool|null} | null,
  "business": {"total_users": number|null, "peak_concurrent_users": number|null, "notes": str|null} | null,
  "assumptions": [{"field": "<section.field>", "requested_value": "<raw text as given in the source>", "used_value": "<the value you mapped it to>", "reason": "<short plain-English reason>"}],
  "unmapped": [{"sheet": "<sheet name>", "label": "<raw header/label text>", "value": "<raw value text>", "reason": "<why you could not confidently map this>"}]
}
Only add an `assumptions` entry when you had to interpret or convert a \
value (e.g. "2 Cores" -> vcpu: 2, or a synonym mapping above); never add \
one for a value that was already an exact, unambiguous match. Put anything \
you are not confident about into `unmapped` instead of guessing at a section field.
"""


class ExtractionService:
    def __init__(self, provider: LLMProvider | None, model: str | None):
        self._provider = provider
        self.model = model

    def extract(self, file_bytes: bytes) -> tuple[CustomerRequirement | None, list[ParseIssue], list[Assumption], str, str]:
        """Returns (requirement, issues, assumptions, source, region_source).
        `source` is "template" when the platform's own strict parser
        recognized the workbook (no LLM call made at all), "ai" when Groq
        extraction produced a usable requirement, or "unrecognized" when
        neither did. `region_source` is "workbook" or "default" - see
        app/domain/region_resolution.py; "default" whenever `requirement`
        is None, since there's nothing to label in that case."""
        requirement, template_issues, region_source = ExcelQuestionnaireParser().parse(file_bytes)
        template_sections = {
            key: getattr(requirement, key).model_dump() if requirement and getattr(requirement, key) else None
            for key in ("compute", "storage", "database", "network", "kubernetes", "availability", "business")
        }
        if has_any_section(template_sections):
            return requirement, template_issues, [], "template", region_source

        if self._provider is None:
            return None, [ParseIssue(field="workbook", message=UNMAPPABLE_MESSAGE, severity=Severity.BLOCKER)], [], "unrecognized", "default"

        workbook_text = dump_workbook_text(file_bytes)
        parsed = self._complete(workbook_text)
        if parsed is None:
            return None, [ParseIssue(field="workbook", message=UNMAPPABLE_MESSAGE, severity=Severity.BLOCKER)], [], "unrecognized", "default"

        return self._build_from_extraction(parsed)

    # -- Groq call ------------------------------------------------------------

    def _complete(self, workbook_text: str) -> dict | None:
        try:
            raw = self._provider.complete_json(system_prompt=_SYSTEM_PROMPT, user_prompt=workbook_text)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Groq extraction response was not a JSON object.")
            return parsed
        except LLMProviderError as exc:
            logger.warning("ExtractionService: Groq call failed, cannot extract this workbook: %s", exc)
            return None
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("ExtractionService: could not parse Groq extraction response: %s", exc)
            return None

    # -- Turning Groq's JSON into a validated CustomerRequirement --------------

    def _build_from_extraction(self, parsed: dict) -> tuple[CustomerRequirement | None, list[ParseIssue], list[Assumption], str, str]:
        issues: list[ParseIssue] = []
        top_level: dict = {}
        sections: dict[str, dict] = {}

        project_name = parsed.get("project_name")
        if isinstance(project_name, str) and project_name.strip():
            top_level["project_name"] = project_name.strip()

        region_hint = parsed.get("region_hint")
        if region_hint:
            try:
                top_level["region"] = coerce_value(region_hint, _REGION_SPEC)
            except (TypeError, ValueError):
                pass  # not a recognized region string - the user picks one explicitly before pricing anyway

        for (section_key, field_key), spec in _SPEC_BY_SECTION_FIELD.items():
            section_obj = parsed.get(section_key)
            if not isinstance(section_obj, dict):
                continue
            raw_value = section_obj.get(field_key)
            if raw_value is None:
                continue
            try:
                coerced = coerce_value(raw_value, spec)
            except (TypeError, ValueError):
                issues.append(ParseIssue(
                    field=spec.label,
                    message=f"AI extraction found '{raw_value}' for {spec.label}, but it could not be interpreted as a {spec.value_type} value; this field was skipped.",
                    severity=Severity.WARNING,
                ))
                continue
            sections.setdefault(section_key, {})[field_key] = coerced

        assumptions = [
            Assumption(
                field=str(a.get("field") or "unknown"),
                requested_value=str(a.get("requested_value") or ""),
                used_value=str(a.get("used_value") or ""),
                reason=str(a.get("reason") or "Interpreted from the uploaded workbook by AI-assisted extraction."),
                strategy_applied="ai_extraction",
            )
            for a in parsed.get("assumptions") or []
            if isinstance(a, dict)
        ]

        for u in parsed.get("unmapped") or []:
            if not isinstance(u, dict):
                continue
            sheet = u.get("sheet") or "workbook"
            label = u.get("label") or "unknown field"
            value = u.get("value")
            reason = u.get("reason") or "Could not be confidently mapped to a known requirement field."
            issues.append(ParseIssue(
                field=f"{sheet}.{label}",
                message=f"Could not confidently map '{label}' (value: '{value}') from sheet '{sheet}': {reason} Please review and add it manually if needed.",
                severity=Severity.WARNING,
            ))

        if not has_any_section(sections):
            issues.append(ParseIssue(field="workbook", message=UNMAPPABLE_MESSAGE, severity=Severity.BLOCKER))
            return None, issues, assumptions, "unrecognized", "default"

        requirement, build_issues, region_source = build_customer_requirement(top_level, sections)
        return requirement, issues + build_issues, assumptions, "ai", region_source


def get_extraction_service() -> ExtractionService:
    from app.core.config import get_settings
    from app.llm.factory import get_llm_provider

    settings = get_settings()
    return ExtractionService(provider=get_llm_provider(), model=settings.groq_model)
