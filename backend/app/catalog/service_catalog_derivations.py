"""Computes non-user-facing config values from the raw inputs a customer
actually fills in, for the handful of catalog services whose pricing depends
on a formula rather than a single flat quantity/price multiplication.

Runs once per selection, right before `GenericServicePricingCalculator`
prices it (see `generic_pricing.py`). The keys this writes (e.g.
`vcpu_seconds_per_month`) are referenced by a service's `pricing_dimensions`
but deliberately absent from its `configuration_schema`, so they're never
shown on the form and never required by validation - the customer enters
requests/duration/concurrency, not pre-computed vCPU-seconds.

Pure function, no I/O: `apply_computed_fields(service_id, config) -> config`
always returns a new dict and never mutates its input.
"""
from typing import Any

from app.core.constants import HOURS_PER_MONTH

_SECONDS_PER_MONTH = HOURS_PER_MONTH * 3600

# Cloud Functions (2nd gen, runs on Cloud Run infrastructure) ties the
# allocated vCPU to the selected memory tier rather than letting it be
# chosen independently - this mirrors Google's published memory/CPU pairing
# for gen2 functions (see Cloud Functions "Memory allocation" docs).
_CLOUD_RUN_FUNCTIONS_VCPU_BY_MEMORY_MB = {
    128: 0.083,
    256: 0.167,
    512: 0.333,
    1024: 0.583,
    2048: 1.0,
    4096: 2.0,
    8192: 2.0,
    16384: 4.0,
    32768: 8.0,
}


def _num(config: dict[str, Any], field_id: str, default: float = 0.0) -> float:
    value = config.get(field_id)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _derive_cloud_run(config: dict[str, Any]) -> dict[str, Any]:
    """Billable compute time = (requests x avg duration) / concurrency - the
    same concurrency-adjusted formula Google's own Cloud Run pricing
    calculator uses, since concurrent requests on one instance share the
    same allocated CPU/memory time rather than each billing it separately.

    When `cpu_allocation` is "always_allocated", the instance's CPU/memory
    stay billed for its full lifetime rather than being throttled between
    requests, so idle `min_instances` are never free - billable time is
    floored at `min_instances` running for the whole month. With the default
    "request_only" allocation, Cloud Run throttles CPU outside of request
    processing, so idle warm instances add no compute cost (only the
    request-processing time above is billed)."""
    config = dict(config)
    requests = _num(config, "requests_per_month")
    duration_s = _num(config, "avg_duration_ms") / 1000
    concurrency = max(_num(config, "concurrency", 1.0), 1.0)
    vcpu_count = _num(config, "vcpu_count")
    memory_gb = _num(config, "memory_gb")
    min_instances = _num(config, "min_instances")

    request_processing_seconds = requests * duration_s / concurrency
    if config.get("cpu_allocation") == "always_allocated":
        idle_floor_seconds = min_instances * _SECONDS_PER_MONTH
        billable_seconds = max(request_processing_seconds, idle_floor_seconds)
    else:
        billable_seconds = request_processing_seconds

    config["vcpu_seconds_per_month"] = billable_seconds * vcpu_count
    config["gb_seconds_per_month"] = billable_seconds * memory_gb
    # Constant quantity of 1 for the VPC connector dimension, which is
    # entirely priced through rate_by_option on `vpc_connector_size` rather
    # than by any quantity the customer enters.
    config["vpc_connector_flag"] = 1.0
    return config


def _derive_cloud_run_functions(config: dict[str, Any]) -> dict[str, Any]:
    """Same concurrency-free version of the Cloud Run formula (Cloud
    Functions has no user-configurable concurrency - each invocation gets
    its own instance by default), plus the memory->vCPU tier lookup Google
    applies automatically for gen2 functions."""
    config = dict(config)
    invocations = _num(config, "invocations_per_month")
    duration_s = _num(config, "avg_execution_time_ms") / 1000
    memory_mb = _num(config, "memory_mb", 256.0)
    vcpu = _CLOUD_RUN_FUNCTIONS_VCPU_BY_MEMORY_MB.get(int(memory_mb), memory_mb / 1024 * 1.0)

    billable_seconds = invocations * duration_s
    config["gb_seconds_per_month"] = billable_seconds * (memory_mb / 1024)
    config["vcpu_seconds_per_month"] = billable_seconds * vcpu
    return config


def _derive_alloydb(config: dict[str, Any]) -> dict[str, Any]:
    """`ram_gb` defaults to AlloyDB's standard 8 GB/vCPU ratio when left
    blank, and the read pool's total billable vCPU is nodes x vCPU/node
    (the schema captures those as two separate customer-facing inputs, but
    only their product is a priceable quantity)."""
    config = dict(config)
    if not config.get("ram_gb"):
        config["ram_gb"] = _num(config, "vcpu") * 8
    config["read_pool_total_vcpu"] = _num(config, "read_pool_nodes") * _num(config, "read_pool_vcpu_per_node")
    return config


def _derive_spanner(config: dict[str, Any]) -> dict[str, Any]:
    """Spanner capacity can be requested as raw Processing Units (100 PU
    granularity) or as whole Nodes - 1 node is defined as exactly 1000 PUs,
    so "nodes" mode is just a friendlier input that resolves to the same
    `processing_units` dimension the pricing table already prices."""
    if config.get("capacity_mode") != "nodes":
        return config
    config = dict(config)
    config["processing_units"] = _num(config, "node_count", 1.0) * 1000
    return config


def _derive_dataproc(config: dict[str, Any]) -> dict[str, Any]:
    """Dataproc's management premium is billed per vCPU-hour across the whole
    cluster, not per node - the customer-facing inputs are the VM spec (vCPU
    per node, node count) and how long the cluster runs, which multiply out
    to the same `vcpu_hours_per_month` dimension the pricing table prices."""
    config = dict(config)
    config["vcpu_hours_per_month"] = (
        _num(config, "node_vcpu") * _num(config, "node_count") * _num(config, "cluster_hours_per_month")
    )
    return config


def _derive_gpu(config: dict[str, Any]) -> dict[str, Any]:
    """GPU cost scales with both how many GPUs are attached per host and how
    long each one runs - the customer-facing inputs are `gpu_count` (Count)
    and `gpu_hours_per_month` (Execution time), which multiply out to the
    same `gpu_hours_total_per_month` dimension the pricing table prices."""
    config = dict(config)
    config["gpu_hours_total_per_month"] = _num(config, "gpu_count", 1.0) * _num(config, "gpu_hours_per_month")
    return config


def _derive_tpu(config: dict[str, Any]) -> dict[str, Any]:
    """TPU cost scales with both the configuration topology's chip count
    (encoded as the numeric value of the `tpu_topology` select, e.g. "16" for
    a 4x4 slice) and how long the topology runs - these multiply out to the
    same `tpu_chip_hours_total_per_month` dimension the pricing table prices."""
    config = dict(config)
    config["tpu_chip_hours_total_per_month"] = _num(config, "tpu_topology", 1.0) * _num(config, "tpu_hours_per_month")
    return config


_DERIVATIONS = {
    "cloud-run": _derive_cloud_run,
    "cloud-run-functions": _derive_cloud_run_functions,
    "alloydb": _derive_alloydb,
    "spanner": _derive_spanner,
    "dataproc": _derive_dataproc,
    "gpu": _derive_gpu,
    "tpu": _derive_tpu,
}


def apply_computed_fields(service_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Every service gets `_unit_flag` (a constant 1) available for free, so
    a `PricingDimension` can price a flat monthly fee that varies only by a
    `rate_by_option` selector (e.g. a subscription tier) without scaling by
    an unrelated count field - see Cloud Armor's Managed Protection Plus fee
    and Load Balancing's per-type base fee in service_definitions.py."""
    config = {**config, "_unit_flag": 1.0}
    derive = _DERIVATIONS.get(service_id)
    return derive(config) if derive else config
