from app.domain.enums import GpuType, MachineFamily, MachineTypeKind, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement
from app.validation.engine import ValidationRuleEngine


def make_requirement(**overrides):
    base = dict(project_name="Test Project", region=Region.US_CENTRAL1)
    base.update(overrides)
    return CustomerRequirement(**base)


def test_cpu_validation_flags_unsupported_vcpu(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10))
    report = ValidationRuleEngine().run(req, catalog)
    cpu_results = [r for r in report.results if r.rule == "cpu_validation"]
    assert len(cpu_results) == 1
    assert cpu_results[0].is_valid is False
    assert cpu_results[0].requested_value == "3"
    assert cpu_results[0].severity.value == "warning"


def test_cpu_validation_passes_for_supported_vcpu(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    report = ValidationRuleEngine().run(req, catalog)
    cpu_results = [r for r in report.results if r.rule == "cpu_validation"]
    assert cpu_results[0].is_valid is True


def test_region_validation_blocks_region_the_catalog_no_longer_supports(catalog):
    """The Region enum only allows known-good region codes, so the way an
    unsupported region reaches validation in practice is a catalog/enum drift
    (e.g. a region deprecated in the catalog before the enum is updated).
    We simulate that by asking a catalog that reports the region unsupported."""

    class DriftedCatalog:
        def __getattr__(self, item):
            return getattr(catalog, item)

        def is_region_supported(self, region_code: str) -> bool:
            return False

    req = make_requirement(region=Region.US_CENTRAL1)
    report = ValidationRuleEngine().run(req, DriftedCatalog())
    region_results = [r for r in report.results if r.rule == "region_validation"]
    assert region_results[0].severity.value == "blocker"
    assert region_results[0].is_valid is False


def test_machine_family_region_validation_blocks_unavailable_combination(catalog):
    """N4A (Arm/Axion) only launches in us-central1/europe-west4 per the mock
    catalog's MachineFamilyCapability.available_regions - asking for it in a
    region outside that list must BLOCK, not silently reprice in another
    region or swap to a different family."""
    req = make_requirement(
        region=Region.ASIA_SOUTH1,
        compute=ComputeRequirement(machine_family=MachineFamily.N4A, vcpu=4, ram_gb=16),
    )
    report = ValidationRuleEngine().run(req, catalog)
    region_results = [r for r in report.results if r.rule == "machine_family_region_validation"]
    assert len(region_results) == 1
    assert region_results[0].is_valid is False
    assert region_results[0].severity.value == "blocker"
    assert "us-central1" in region_results[0].supported_value
    assert report.has_blockers is True


def test_machine_family_region_validation_passes_in_supported_region(catalog):
    req = make_requirement(
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.N4A, vcpu=4, ram_gb=16),
    )
    report = ValidationRuleEngine().run(req, catalog)
    region_results = [r for r in report.results if r.rule == "machine_family_region_validation"]
    assert region_results[0].is_valid is True


def test_machine_family_region_validation_passes_for_family_with_no_region_restriction(catalog):
    """`available_regions is None` means "available everywhere the catalog
    supports" (see MachineFamilyCapability's docstring) - the common case for
    well-established families like N2."""
    req = make_requirement(
        region=Region.ASIA_SOUTH1,
        compute=ComputeRequirement(machine_family=MachineFamily.N2, vcpu=4, ram_gb=16),
    )
    report = ValidationRuleEngine().run(req, catalog)
    region_results = [r for r in report.results if r.rule == "machine_family_region_validation"]
    assert region_results[0].is_valid is True


def test_machine_family_region_validation_uses_named_machine_types_own_family(catalog):
    """A directly-named `machine_type` (e.g. "t2a-standard-4") is checked
    against *its own* family's region availability, not the (possibly
    unrelated) declared `machine_family` - mirrors NormalizationEngine's own
    precedence (see _effective_family in app/validation/rules.py)."""
    req = make_requirement(
        region=Region.ASIA_SOUTH1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, machine_type="t2a-standard-4", vcpu=4, ram_gb=16),
    )
    report = ValidationRuleEngine().run(req, catalog)
    region_results = [r for r in report.results if r.rule == "machine_family_region_validation"]
    assert region_results[0].is_valid is False
    assert "t2a" in region_results[0].requested_value


def test_gpu_validation_blocks_incompatible_family(catalog):
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, gpu_type=GpuType.NVIDIA_A100_40GB, gpu_count=1,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    gpu_results = [r for r in report.results if r.rule == "gpu_validation"]
    assert any(r.severity.value == "blocker" for r in gpu_results)


def test_gpu_validation_passes_for_compatible_family(catalog):
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.A2, vcpu=12, ram_gb=85, gpu_type=GpuType.NVIDIA_A100_40GB, gpu_count=1,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    gpu_results = [r for r in report.results if r.rule == "gpu_validation"]
    assert all(r.is_valid for r in gpu_results)


def test_availability_flags_impossible_uptime(catalog):
    from app.domain.requirements import AvailabilityRequirement
    req = make_requirement(availability=AvailabilityRequirement(target_uptime_percent=99.999))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "availability_validation"]
    assert results[0].is_valid is False


# -- Machine type: predefined-by-name / custom shapes ------------------------

def test_machine_type_validation_passes_for_known_predefined_type(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.N4, machine_type="n4-standard-4"))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "machine_type_validation"]
    assert results[0].is_valid is True


def test_machine_type_validation_blocks_unknown_name(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.N4, machine_type="n4-does-not-exist"))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "machine_type_validation"]
    assert results[0].is_valid is False
    assert results[0].severity.value == "blocker"


def test_custom_machine_type_validation_passes_for_supported_shape(catalog):
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.N2D, vcpu=2, ram_gb=4, machine_type_kind=MachineTypeKind.CUSTOM,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "custom_machine_type_validation"]
    assert results[0].is_valid is True


def test_custom_machine_type_validation_blocks_unsupported_family(catalog):
    # T2D does not support custom machine types on real Google Cloud.
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.T2D, vcpu=4, ram_gb=16, machine_type_kind=MachineTypeKind.CUSTOM,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "custom_machine_type_validation"]
    assert results[0].is_valid is False
    assert results[0].severity.value == "blocker"
    assert "does not support custom" in results[0].reason


def test_custom_machine_type_validation_blocks_out_of_range_vcpu(catalog):
    # N2D custom requires an even vCPU count >= 2.
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.N2D, vcpu=3, ram_gb=4, machine_type_kind=MachineTypeKind.CUSTOM,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "custom_machine_type_validation"]
    assert results[0].is_valid is False
    assert results[0].severity.value == "blocker"


def test_custom_machine_type_validation_blocks_out_of_range_ram_ratio(catalog):
    # E2 custom RAM/vCPU ratio must be within 0.5-8 GB/vCPU.
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.E2, vcpu=2, ram_gb=64, machine_type_kind=MachineTypeKind.CUSTOM,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    results = [r for r in report.results if r.rule == "custom_machine_type_validation"]
    assert results[0].is_valid is False


def test_legacy_cpu_ram_family_rules_skip_explicit_custom_requests(catalog):
    # A custom shape is *expected* not to match any predefined vCPU/RAM
    # pairing - that's the point - so the legacy rules must not also flag it.
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.N2D, vcpu=2, ram_gb=4, machine_type_kind=MachineTypeKind.CUSTOM,
    ))
    report = ValidationRuleEngine().run(req, catalog)
    assert [r for r in report.results if r.rule == "cpu_validation"] == []
    assert [r for r in report.results if r.rule == "ram_validation"] == []
    assert [r for r in report.results if r.rule == "machine_family_validation"] == []
