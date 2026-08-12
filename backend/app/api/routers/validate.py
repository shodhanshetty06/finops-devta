"""Validation-only endpoint - runs the rule engine without pricing, useful
for a live "as you type" questionnaire experience on the frontend."""
from fastapi import APIRouter, Depends

from app.catalog.base import CatalogProvider
from app.catalog.dependency import get_catalog_provider
from app.domain.requirements import CustomerRequirement
from app.domain.validation import ValidationReport
from app.validation.engine import ValidationRuleEngine

router = APIRouter(prefix="/api/v1", tags=["Validation"])


@router.post("/validate", response_model=ValidationReport, summary="Validate a customer requirement without pricing it")
def validate(requirement: CustomerRequirement, catalog: CatalogProvider = Depends(get_catalog_provider)):
    engine = ValidationRuleEngine()
    return engine.run(requirement, catalog)
