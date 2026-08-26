"""
Parses a filled-in questionnaire workbook (see `excel_template.py`) into a
`CustomerRequirement`.

Design principle carried over from the validation/normalization engines:
never trust the input, and never let one bad cell blow up the whole parse.
A typo in the Database section still lets the Compute section come through
cleanly - the caller sees exactly which section/field failed and why via
`ParseIssue`, the same "always explain, never hide" philosophy as
`Assumption` and `ValidationResult`.

Only understands this platform's own template (labels in column A, values
in column B, matched by exact label text) - a customer's own arbitrary
workbook layout won't match these labels and will simply parse as empty.
See app/services/extraction_service.py for the Groq-based fallback that
handles that case.
"""
import io

import openpyxl

from app.core.exceptions import IntakeParseError
from app.domain.enums import Severity
from app.domain.intake import ParseIssue
from app.domain.requirements import CustomerRequirement
from app.intake.build import build_customer_requirement, coerce_value
from app.intake.schema import FIELD_SCHEMA, SECTION_KEYS


class ExcelQuestionnaireParser:
    def parse(self, file_bytes: bytes) -> tuple[CustomerRequirement | None, list[ParseIssue]]:
        raw_values = self._read_cells(file_bytes)
        issues: list[ParseIssue] = []

        top_level: dict = {}
        sections: dict[str, dict] = {key: {} for key in SECTION_KEYS.values()}

        label_lookup = {spec.label.strip().lower(): spec for spec in FIELD_SCHEMA}

        for label, raw_value in raw_values.items():
            spec = label_lookup.get(label)
            if spec is None or raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
                continue

            try:
                coerced = coerce_value(raw_value, spec)
            except (TypeError, ValueError):
                issues.append(ParseIssue(
                    field=spec.label,
                    message=f"Could not interpret '{raw_value}' as a {spec.value_type} value; this field was skipped.",
                    severity=Severity.WARNING,
                ))
                continue

            if len(spec.path) == 1:
                top_level[spec.path[0]] = coerced
            else:
                section_key, field_key = spec.path
                sections[section_key][field_key] = coerced

        requirement, build_issues = build_customer_requirement(top_level, sections)
        return requirement, issues + build_issues

    def _read_cells(self, file_bytes: bytes) -> dict[str, object]:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        except Exception as exc:  # openpyxl raises several distinct types for corrupt files
            raise IntakeParseError(
                "The uploaded file is not a valid Excel (.xlsx) workbook, or could not be opened."
            ) from exc

        ws = None
        for name in wb.sheetnames:
            if name.strip().lower() == "questionnaire":
                ws = wb[name]
                break
        if ws is None:
            ws = wb[wb.sheetnames[0]]

        values: dict[str, object] = {}
        for row in ws.iter_rows():
            if len(row) < 2:
                continue
            label_cell, value_cell = row[0], row[1]
            if label_cell.value is None:
                continue
            label = str(label_cell.value).strip().lower()
            values[label] = value_cell.value
        return values
