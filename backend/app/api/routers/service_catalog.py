"""Read-only endpoint exposing the generic GCP service catalog
(app/catalog/service_definitions.py) - the data source for the New Estimate
page's searchable, categorized service picker and its dynamic, schema-driven
configuration forms."""
from fastapi import APIRouter, Query

from app.catalog.service_catalog import GCPServiceDefinition
from app.catalog.service_definitions import GCP_SERVICE_CATALOG, SERVICE_CATEGORIES

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


@router.get("/services", summary="Search/list the GCP service catalog", response_model=list[GCPServiceDefinition])
def list_services(
    search: str | None = Query(default=None, description="Case-insensitive substring match on name/description"),
    category: str | None = Query(default=None, description="Exact category match"),
):
    results = [s for s in GCP_SERVICE_CATALOG if s.active]
    if category:
        results = [s for s in results if s.category == category]
    if search:
        needle = search.lower()
        results = [
            s for s in results
            if needle in s.display_name.lower() or needle in s.description.lower()
        ]
    return results


@router.get("/services/categories", summary="List service catalog categories in display order")
def list_service_categories():
    return SERVICE_CATEGORIES
