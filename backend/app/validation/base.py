"""Validation rule interface. Every concrete rule implements `evaluate` and
returns zero or more ValidationResult objects - one per field it inspects.
Rules must never raise for "invalid" input; a BLOCKER-severity result is how
an unsatisfiable request is communicated up the stack."""
from abc import ABC, abstractmethod

from app.catalog.base import CatalogProvider
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationResult


class ValidationRule(ABC):
    name: str

    @abstractmethod
    def evaluate(
        self, requirement: CustomerRequirement, catalog: CatalogProvider
    ) -> list[ValidationResult]: ...
