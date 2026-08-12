"""Read-only endpoints exposing what the platform currently considers a
'supported' Google Cloud configuration - useful for building questionnaire
dropdowns on the frontend."""
from fastapi import APIRouter, Depends, Query

from app.catalog.base import CatalogProvider
from app.catalog.dependency import get_catalog_provider

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


@router.get("/machine-types", summary="List supported Compute Engine machine types")
def list_machine_types(family: str | None = Query(default=None), catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.list_machine_types(family=family)


@router.get("/disk-types", summary="List supported Persistent Disk types")
def list_disk_types(catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.list_disk_types()


@router.get("/gpu-types", summary="List supported GPU accelerators")
def list_gpu_types(catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.list_gpu_types()


@router.get("/regions", summary="List supported Google Cloud regions")
def list_regions(catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.list_regions()


@router.get("/cloud-sql-tiers", summary="List supported Cloud SQL tiers")
def list_cloud_sql_tiers(engine: str | None = Query(default=None), catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.list_cloud_sql_tiers(engine=engine)


@router.get("/gke-config", summary="GKE cluster configuration limits")
def gke_config(catalog: CatalogProvider = Depends(get_catalog_provider)):
    return catalog.get_gke_config()
