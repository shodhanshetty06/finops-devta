from app.core.config import Settings
from app.domain.enums import MachineFamily, Region
from app.domain.estimate import NormalizedDisk, NormalizedSpec
from app.domain.requirements import ComputeRequirement, CustomerRequirement, NetworkRequirement
from app.pricing.engine import PricingEngine, HOURS_PER_MONTH


def test_compute_line_item_matches_provider_price(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0, instance_count=2)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)

    expected_hourly = pricing_provider.get_compute_hourly_price_for_spec(4, 16.0, "e2", "us-central1")
    compute_items = [li for li in cost.line_items if li.category == "Compute"]
    assert len(compute_items) == 1
    assert compute_items[0].unit_price == expected_hourly
    assert compute_items[0].monthly_amount == round(expected_hourly * HOURS_PER_MONTH * 2, 2)


def test_sustained_use_discount_applied_by_default(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0, instance_count=1)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings, commitment_term_years=0)
    assert any(d.name == "Sustained Use Discount" for d in cost.discounts)
    assert cost.discount_total_monthly > 0
    assert cost.total_monthly == round(cost.subtotal_monthly - cost.discount_total_monthly, 2)


def test_committed_use_discount_replaces_sustained_use(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0, instance_count=1)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings, commitment_term_years=3)
    assert len(cost.discounts) == 1
    assert "3-Year" in cost.discounts[0].name


def test_yearly_and_three_year_totals_derive_from_monthly(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-2", vcpu=2, ram_gb=8.0, instance_count=1)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=2, ram_gb=8))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)
    assert cost.total_yearly == round(cost.total_monthly * 12, 2)
    assert cost.total_three_year == round(cost.total_monthly * 36, 2)


def test_tax_and_support_applied(pricing_provider):
    settings = Settings(default_tax_rate_percent=10, support_plan_percent=5)
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-2", vcpu=2, ram_gb=8.0, instance_count=1)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=2, ram_gb=8))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)
    assert cost.tax_monthly > 0
    assert cost.support_monthly > 0
    after_discount = round(cost.subtotal_monthly - cost.discount_total_monthly, 2)
    assert cost.total_monthly == round(after_discount + cost.tax_monthly + cost.support_monthly, 2)


def test_gpu_line_item_added_when_gpu_requested(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="a2-highgpu-1g", vcpu=12, ram_gb=85.0,
                           instance_count=1, gpu_type="nvidia-tesla-a100", gpu_count=1)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.A2, vcpu=12, ram_gb=85,
                                                           gpu_type="nvidia-tesla-a100", gpu_count=1))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)
    gpu_items = [li for li in cost.line_items if li.category == "GPU"]
    assert len(gpu_items) == 1
    assert gpu_items[0].monthly_amount > 0


def test_spot_discount_replaces_sustained_use_and_is_mutually_exclusive_with_cud(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0,
                           instance_count=1, family="e2", provisioning_model="spot")
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))
    # Even though a 3-year commitment is also passed, Spot must win.
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings, commitment_term_years=3)
    assert len(cost.discounts) == 1
    assert cost.discounts[0].name == "Spot/Preemptible VM Discount"
    expected_percent = pricing_provider.get_spot_discount_percent("e2")
    assert cost.discounts[0].percent_off == expected_percent
    compute_amount = next(li.monthly_amount for li in cost.line_items if li.category == "Compute")
    assert cost.discounts[0].monthly_savings == round(compute_amount * expected_percent / 100, 2)


def test_partial_month_duration_reduces_compute_but_not_storage(pricing_provider, settings):
    running_hours = 176.0  # 8 hours/day x 22 days/month
    spec_full = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0,
                                instance_count=1, disk_type="pd-balanced", disk_size_gb=100)
    spec_partial = spec_full.model_copy(update={"running_hours_per_month": running_hours})
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))

    cost_full = PricingEngine().calculate(spec_full, req, pricing_provider, settings)
    cost_partial = PricingEngine().calculate(spec_partial, req, pricing_provider, settings)

    compute_full = next(li for li in cost_full.line_items if li.category == "Compute")
    compute_partial = next(li for li in cost_partial.line_items if li.category == "Compute")
    assert compute_partial.quantity == running_hours
    assert compute_partial.monthly_amount == round(compute_full.unit_price * running_hours, 2)
    assert compute_partial.monthly_amount < compute_full.monthly_amount

    storage_full = next(li for li in cost_full.line_items if li.category == "Storage")
    storage_partial = next(li for li in cost_partial.line_items if li.category == "Storage")
    assert storage_partial.monthly_amount == storage_full.monthly_amount


def test_os_licensing_line_item_added_for_windows_but_not_linux(pricing_provider, settings):
    spec_linux = NormalizedSpec(region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0,
                                 instance_count=1, operating_system="linux")
    spec_windows = spec_linux.model_copy(update={"operating_system": "windows_server"})
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16))

    cost_linux = PricingEngine().calculate(spec_linux, req, pricing_provider, settings)
    cost_windows = PricingEngine().calculate(spec_windows, req, pricing_provider, settings)

    assert not any(li.category == "Licensing" for li in cost_linux.line_items)
    license_item = next(li for li in cost_windows.line_items if li.category == "Licensing")
    expected_hourly = pricing_provider.get_os_license_hourly_price("windows_server", 4)
    assert license_item.monthly_amount == round(expected_hourly * HOURS_PER_MONTH, 2)
    # OS licensing is a third-party software cost, not GCP infrastructure -
    # it must never be discounted by Sustained/Committed/Spot discounts.
    assert cost_windows.total_monthly > cost_linux.total_monthly


def test_local_ssd_and_additional_disks_priced_as_storage(pricing_provider, settings):
    spec = NormalizedSpec(
        region="us-central1", machine_type="e2-standard-4", vcpu=4, ram_gb=16.0, instance_count=2,
        disk_type="pd-balanced", disk_size_gb=100,
        additional_disks=[NormalizedDisk(disk_type="pd-ssd", size_gb=50)],
        local_ssd_count=2,
    )
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=4, ram_gb=16, instance_count=2))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)

    storage_items = [li for li in cost.line_items if li.category == "Storage"]
    assert len(storage_items) == 3  # boot disk + additional disk + local SSD

    local_ssd_item = next(li for li in storage_items if li.sku_id == "local-ssd")
    expected_per_disk = pricing_provider.get_local_ssd_monthly_price_per_disk("us-central1")
    assert local_ssd_item.monthly_amount == round(expected_per_disk * 2 * 2, 2)  # 2 blocks x 2 instances

    extra_disk_item = next(li for li in storage_items if li.sku_id == "disk-pd-ssd")
    expected_extra_price = pricing_provider.get_disk_monthly_price_per_gb("pd-ssd", "us-central1")
    assert extra_disk_item.monthly_amount == round(expected_extra_price * 50 * 2, 2)  # 50 GB x 2 instances


def test_static_ip_priced_per_reserved_address(pricing_provider, settings):
    spec = NormalizedSpec(region="us-central1", machine_type="e2-standard-2", vcpu=2, ram_gb=8.0,
                           instance_count=1, static_ip_count=3)
    req = CustomerRequirement(project_name="p", region=Region.US_CENTRAL1,
                               compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=2, ram_gb=8),
                               network=NetworkRequirement(external_ip_count=3))
    cost = PricingEngine().calculate(spec, req, pricing_provider, settings)
    ip_item = next(li for li in cost.line_items if li.sku_id == "static-ip")
    expected_price = pricing_provider.get_static_ip_monthly_price("us-central1")
    assert ip_item.monthly_amount == round(expected_price * 3, 2)
    assert ip_item.quantity == 3
