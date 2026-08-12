"""Bridges catalog service selections that overlap with the legacy typed
schema (Persistent Disk, Cloud SQL, GKE) into StorageRequirement/
DatabaseRequirement/KubernetesRequirement, so the rest of the pipeline
(validation, normalization, pricing) treats them exactly like a classic
/questionnaire submission and keeps using the real, exact PricingProvider -
never a duplicated or approximated calculation for services that already
have one. Networking services (Load Balancing, Cloud CDN, VPN, Cloud NAT,
Cloud Armor, Cloud DNS, Interconnect, VPC, Network egress) have no legacy
typed model and are priced generically instead (see
app/catalog/generic_pricing.py).

This is the ONLY place in the platform that branches on a specific
`service_id` - every other consumer of the catalog (validation rule,
generic pricing calculator, frontend rendering) is driven purely by
`GCPServiceDefinition.configuration_schema`/`pricing_dimensions`.
"""
from app.catalog.service_definitions import SERVICE_CATALOG_BY_ID
from app.domain.requirements import (
    CustomerRequirement,
    DatabaseRequirement,
    KubernetesRequirement,
    ServiceSelection,
    StorageRequirement,
)


def apply_bridged_services(
    requirement: CustomerRequirement,
) -> tuple[CustomerRequirement, list[ServiceSelection]]:
    """Returns (requirement with bridged legacy fields populated, the
    selections that have no legacy equivalent and must go through the
    generic pricing/validation path instead)."""
    if not requirement.selected_services:
        return requirement, []

    storage_selection: ServiceSelection | None = None
    database_selection: ServiceSelection | None = None
    kubernetes_selection: ServiceSelection | None = None
    remaining: list[ServiceSelection] = []

    for selection in requirement.selected_services:
        definition = SERVICE_CATALOG_BY_ID.get(selection.service_id)
        binding = definition.legacy_binding if definition else None
        if binding == "storage" and storage_selection is None:
            storage_selection = selection
        elif binding == "database" and database_selection is None:
            database_selection = selection
        elif binding == "kubernetes" and kubernetes_selection is None:
            kubernetes_selection = selection
        else:
            remaining.append(selection)

    updates: dict = {}
    if storage_selection and requirement.storage is None:
        updates["storage"] = StorageRequirement.model_validate(storage_selection.config)
    if database_selection and requirement.database is None:
        updates["database"] = DatabaseRequirement.model_validate({**database_selection.config, "required": True})
    if kubernetes_selection and requirement.kubernetes is None:
        updates["kubernetes"] = KubernetesRequirement.model_validate({**kubernetes_selection.config, "required": True})

    if not updates:
        return requirement, remaining
    return requirement.model_copy(update=updates), remaining
