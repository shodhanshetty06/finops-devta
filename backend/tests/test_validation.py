from app.domain.enums import GpuType, MachineFamily, Region
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
