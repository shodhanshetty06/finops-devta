"""RuleEngine: runs every registered ValidationRule against a request and
produces a single ValidationReport."""
from app.catalog.base import CatalogProvider
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationReport
from app.validation.rules import ALL_RULES


class ValidationRuleEngine:
    def __init__(self, rules=None):
        self.rules = rules if rules is not None else ALL_RULES

    def run(self, requirement: CustomerRequirement, catalog: CatalogProvider) -> ValidationReport:
        results = []
        for rule in self.rules:
            results.extend(rule.evaluate(requirement, catalog))
        return ValidationReport(results=results)
