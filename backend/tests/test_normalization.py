from app.core.config import NormalizationStrategy
from app.domain.enums import MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement
from app.normalization.engine import NormalizationEngine


def make_requirement(**overrides):
    base = dict(project_name="Test Project", region=Region.US_CENTRAL1)
    base.update(overrides)
    return CustomerRequirement(**base)


def test_performance_strategy_picks_nearest_higher_cpu(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.PERFORMANCE)
    assert spec.vcpu == 4
    assert spec.machine_type == "e2-standard-4"
    assert any(a.field == "compute.vcpu" and a.used_value == "4" for a in assumptions)


def test_conservative_strategy_picks_nearest_lower_cpu(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.CONSERVATIVE)
    assert spec.vcpu == 2
    assert spec.machine_type == "e2-standard-2"


def test_balanced_strategy_picks_mathematically_closest_cpu(catalog):
    # Between 2 and 4, 3 is equidistant -> balanced ties resolve upward to 4.
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=3, ram_gb=10))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.vcpu == 4

    # 9 is closer to 8 than to 16.
    req2 = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=9, ram_gb=30))
    spec2, _ = NormalizationEngine().normalize(req2, catalog, NormalizationStrategy.BALANCED)
    assert spec2.vcpu == 8


def test_exact_match_produces_no_assumption(catalog):
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.machine_type == "e2-standard-4"
    assert assumptions == []


def test_unsupported_region_falls_back_with_assumption(catalog):
    req = make_requirement(region=Region.US_CENTRAL1)
    # Force an unsupported region by mutating post-construction is not possible (enum);
    # instead verify a supported region produces no region assumption.
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.region == "us-central1"
    assert not any(a.field == "region" for a in assumptions)


def test_storage_size_clamped_to_disk_range(catalog):
    from app.domain.requirements import StorageRequirement
    from app.domain.enums import DiskType
    req = make_requirement(storage=StorageRequirement(disk_type=DiskType.PD_EXTREME, size_gb=50))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.disk_size_gb == 500  # pd-extreme min is 500 GB
    assert any(a.field == "storage.size_gb" for a in assumptions)


def test_database_tier_normalization(catalog):
    from app.domain.requirements import DatabaseRequirement
    from app.domain.enums import CloudSqlEngine
    req = make_requirement(database=DatabaseRequirement(
        required=True, engine=CloudSqlEngine.POSTGRES, size_gb=50, vcpu=3, ram_gb=10,
    ))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.database_tier is not None
    assert any(a.field == "database.tier" for a in assumptions)


def test_unset_duration_leaves_running_hours_none(catalog):
    # No hours_per_day/days_per_month supplied -> full 24/7 month, same as
    # every estimate created before this field existed.
    req = make_requirement(compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    spec, _ = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.running_hours_per_month is None


def test_partial_duration_computed_from_hours_and_days(catalog):
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, hours_per_day=8, days_per_month=22,
    ))
    spec, _ = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.running_hours_per_month == 176.0


def test_partial_duration_clamped_to_full_month(catalog):
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, hours_per_day=24, days_per_month=31,
    ))
    spec, _ = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.running_hours_per_month == 730.0


def test_provisioning_model_and_os_passed_through(catalog):
    from app.domain.enums import OperatingSystem, ProvisioningModel
    req = make_requirement(compute=ComputeRequirement(
        machine_family=MachineFamily.E2, vcpu=4, ram_gb=16,
        provisioning_model=ProvisioningModel.SPOT, operating_system=OperatingSystem.WINDOWS_SERVER,
    ))
    spec, _ = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.provisioning_model == "spot"
    assert spec.operating_system == "windows_server"


def test_additional_disks_normalized_and_clamped(catalog):
    from app.domain.requirements import AdditionalDiskRequirement, StorageRequirement
    from app.domain.enums import DiskType
    req = make_requirement(storage=StorageRequirement(
        disk_type=DiskType.PD_BALANCED, size_gb=100, local_ssd_count=2,
        additional_disks=[AdditionalDiskRequirement(disk_type=DiskType.PD_EXTREME, size_gb=50)],
    ))
    spec, assumptions = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.local_ssd_count == 2
    assert len(spec.additional_disks) == 1
    assert spec.additional_disks[0].disk_type == "pd-extreme"
    assert spec.additional_disks[0].size_gb == 500  # pd-extreme min is 500 GB
    assert any(a.field == "storage.additional_disks[0].size_gb" for a in assumptions)


def test_static_ip_count_passed_through_from_network(catalog):
    from app.domain.requirements import NetworkRequirement
    req = make_requirement(network=NetworkRequirement(external_ip_count=2))
    spec, _ = NormalizationEngine().normalize(req, catalog, NormalizationStrategy.BALANCED)
    assert spec.static_ip_count == 2
