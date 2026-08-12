"""
Celery task for batch estimate pricing - e.g. a consultant pricing dozens of
customer requirements (from a bulk import) in one call instead of one HTTP
request per requirement. Runs the exact same `EstimationService` pipeline
the synchronous `POST /api/v1/estimate` endpoint uses, item by item.

One bad item never fails the whole batch: each requirement is priced
independently and reports its own success/error, the same transparency
philosophy the Phase 4 intake parser uses for partially-bad uploads. A
batch of 50 with 2 unpriceable items still returns 48 priced estimates.
"""
from typing import Any

from app.catalog.dependency import get_catalog_provider
from app.core.config import get_settings
from app.core.exceptions import FinOpsError
from app.domain.requirements import CustomerRequirement
from app.pricing.dependency import get_pricing_provider
from app.services.estimation_service import EstimationService
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.batch_tasks.generate_batch_estimates_task", bind=True)
def generate_batch_estimates_task(
    self,
    requirements_json: list[dict[str, Any]],
    force: bool = False,
    commitment_term_years: int = 0,
) -> dict[str, Any]:
    settings = get_settings()
    service = EstimationService(
        catalog=get_catalog_provider(),
        pricing_provider=get_pricing_provider(),
        settings=settings,
    )

    results: list[dict[str, Any]] = []
    succeeded = 0
    for index, raw_requirement in enumerate(requirements_json):
        try:
            requirement = CustomerRequirement.model_validate(raw_requirement)
            estimate = service.generate_estimate(
                requirement, force=force, commitment_term_years=commitment_term_years,
            )
            results.append({
                "index": index,
                "project_name": raw_requirement.get("project_name"),
                "status": "success",
                "result": estimate.model_dump(mode="json"),
                "error": None,
            })
            succeeded += 1
        except FinOpsError as exc:
            results.append({
                "index": index,
                "project_name": raw_requirement.get("project_name"),
                "status": "error",
                "result": None,
                "error": exc.message,
            })
        except Exception as exc:  # noqa: BLE001 - malformed input shouldn't kill the whole batch
            results.append({
                "index": index,
                "project_name": raw_requirement.get("project_name"),
                "status": "error",
                "result": None,
                "error": str(exc),
            })

    return {
        "total": len(requirements_json),
        "succeeded": succeeded,
        "failed": len(requirements_json) - succeeded,
        "items": results,
    }
