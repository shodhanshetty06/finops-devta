"""
Carbon footprint estimator.

This platform has no live emissions-factor API integration, so this engine
uses a small, explicitly-labeled table of illustrative regional grid carbon
intensity figures (loosely modeled on the real, well-documented spread
between hydro/nuclear-heavy grids like us-west1/Oregon and coal-heavy grids
like asia-south1/Mumbai) and a published-order-of-magnitude estimate of
average server power draw per vCPU. These are ASSUMPTIONS, not measurements
- every `CarbonEstimate` carries a `methodology_note` restating this so the
number is never mistaken for an audited carbon accounting figure. Treat the
output as directionally useful for comparing regions/configurations, not as
a compliance-grade emissions report.
"""
from app.domain.estimate import NormalizedSpec
from app.domain.optimization import CarbonEstimate

HOURS_PER_MONTH = 730

# Illustrative average grid carbon intensity, grams CO2e per kWh, per supported
# region. Real-world grid mix varies hour to hour; these are single
# representative figures for relative comparison only.
GRID_CARBON_INTENSITY_GCO2E_PER_KWH: dict[str, float] = {
    "us-central1": 480.0,       # Iowa - mixed grid, meaningful coal/gas share
    "us-east1": 400.0,          # South Carolina - mixed grid
    "us-west1": 90.0,           # Oregon - hydro-heavy, low carbon
    "europe-west1": 167.0,      # Belgium - nuclear-heavy
    "europe-west4": 350.0,      # Netherlands - gas-heavy
    "asia-south1": 708.0,       # Mumbai - coal-heavy grid
    "asia-southeast1": 408.0,   # Singapore - gas-heavy
}
DEFAULT_GRID_CARBON_INTENSITY = 450.0  # fallback for any unmapped region

WATTS_PER_VCPU = 3.5           # illustrative average modern cloud-server draw per vCPU
DATACENTER_PUE = 1.1           # power usage effectiveness overhead (cooling, etc.)


class CarbonEngine:
    def estimate(self, spec: NormalizedSpec) -> CarbonEstimate:
        vcpu = spec.vcpu or 0
        instance_count = spec.instance_count or (1 if vcpu else 0)
        vcpu_hours = vcpu * instance_count * HOURS_PER_MONTH

        intensity = GRID_CARBON_INTENSITY_GCO2E_PER_KWH.get(spec.region, DEFAULT_GRID_CARBON_INTENSITY)
        kwh = vcpu_hours * (WATTS_PER_VCPU / 1000) * DATACENTER_PUE
        kgco2e = kwh * intensity / 1000

        return CarbonEstimate(
            region=spec.region,
            estimated_vcpu_hours_per_month=round(vcpu_hours, 1),
            grid_carbon_intensity_gco2e_per_kwh=intensity,
            estimated_kwh_per_month=round(kwh, 2),
            estimated_kgco2e_per_month=round(kgco2e, 2),
            methodology_note=(
                f"Illustrative estimate: vCPU-hours x {WATTS_PER_VCPU}W/vCPU x {DATACENTER_PUE} PUE = kWh, "
                f"x {intensity:.0f} gCO2e/kWh (regional grid average for {spec.region}) = kgCO2e. Covers the "
                "primary compute line item only (GKE nodes, Cloud SQL, and storage power draw are not modeled). "
                "Not an audited or certified carbon accounting figure - use for relative comparison only."
            ),
        )
