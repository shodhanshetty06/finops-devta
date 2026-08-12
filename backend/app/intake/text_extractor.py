"""
Natural-language requirement extraction.

Turns free-text business requirements (e.g. "500 users, HA required, 99.99%
uptime, 100GB database") into a `CustomerRequirement`. This is a deliberately
transparent, rule-based (regex/keyword) extractor - NOT a hosted LLM call,
consistent with this platform's core invariant that the AI layer explains
and infers structure but a PricingProvider always supplies the actual
dollar amounts. Swapping this for an LLM-backed extractor later is a
drop-in replacement: the contract is `extract(project_name, text) ->
(CustomerRequirement, list[Assumption])` and nothing downstream cares how
that's implemented.

Every inference is recorded as an `Assumption` (the same model the
normalization engine uses) so a human reviewing the output can see exactly
which phrase in their text produced which structured field - never a silent
guess.
"""
import re

from app.domain.assumption import Assumption
from app.domain.enums import BackupFrequency, CloudSqlEngine, Region
from app.domain.requirements import (
    AvailabilityRequirement,
    BusinessContext,
    CustomerRequirement,
    DatabaseRequirement,
    KubernetesRequirement,
    NetworkRequirement,
)

_USER_COUNT_RE = re.compile(r"(\d[\d,]*)\s*(concurrent\s+)?users", re.IGNORECASE)
_UPTIME_RE = re.compile(
    r"(?:(\d{2,3}(?:\.\d{1,3})?)\s*%\s*(?:uptime|availability|sla))"
    r"|(?:(?:uptime|availability|sla)[^\d%]{0,15}(\d{2,3}(?:\.\d{1,3})?)\s*%)",
    re.IGNORECASE,
)
_DB_SIZE_RE = re.compile(r"(\d+)\s*gb\s*(?:database|db\b|data\s*store)", re.IGNORECASE)
_EGRESS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(gb|tb)\s*(?:of\s+)?(?:bandwidth|egress|traffic|data\s*transfer)"
    r"(?:\s*(?:per|/|a)\s*month)?",
    re.IGNORECASE,
)

_HA_KEYWORDS = ["high availability", "highly available", "multi-zone", "multi zone", "zero downtime", "no downtime", " ha "]
_K8S_KEYWORDS = ["kubernetes", "gke", "container orchestration", "microservices", "docker containers"]
_GPU_KEYWORDS = ["gpu", "machine learning", "ml training", "deep learning", "neural network", "tensorflow", "pytorch", "ai model"]
_DR_KEYWORDS = ["disaster recovery", "business continuity", "dr required", "failover to another region"]
_LB_KEYWORDS = ["load balancer", "load balancing", "high traffic", "auto-scaling", "autoscaling"]
_CDN_KEYWORDS = ["cdn", "content delivery network", "static asset caching", "edge caching"]
_VPN_KEYWORDS = ["vpn", "site-to-site", "private connectivity to on-premises"]

_REGION_KEYWORDS: list[tuple[str, Region]] = [
    ("mumbai", Region.ASIA_SOUTH1), ("india", Region.ASIA_SOUTH1),
    ("singapore", Region.ASIA_SOUTHEAST1), ("southeast asia", Region.ASIA_SOUTHEAST1),
    ("belgium", Region.EUROPE_WEST1), ("europe", Region.EUROPE_WEST1), (" eu ", Region.EUROPE_WEST1),
    ("netherlands", Region.EUROPE_WEST4),
    ("oregon", Region.US_WEST1), ("west coast", Region.US_WEST1),
    ("south carolina", Region.US_EAST1), ("east coast", Region.US_EAST1),
    ("iowa", Region.US_CENTRAL1), ("united states", Region.US_CENTRAL1), ("usa", Region.US_CENTRAL1),
]


class NaturalLanguageRequirementExtractor:
    def extract(
        self, project_name: str, text: str, region_hint: str | None = None,
    ) -> tuple[CustomerRequirement, list[Assumption]]:
        lower = f" {text.lower()} "
        notes: list[Assumption] = []

        region = self._extract_region(lower, region_hint, notes)
        business = self._extract_business_context(lower, text, notes)
        availability = self._extract_availability(lower, notes)
        network = self._extract_network(lower, notes)
        kubernetes = self._extract_kubernetes(lower, notes)
        database = self._extract_database(lower, notes)
        self._note_gpu_workload(lower, notes)

        if database is not None and availability is not None and availability.high_availability:
            database.high_availability = True
            notes.append(Assumption(
                field="database.high_availability", requested_value="(inferred)", used_value="true",
                reason="High availability was requested for the project overall, so the database was marked HA too.",
                strategy_applied="nlp_extraction",
            ))

        requirement = CustomerRequirement(
            project_name=project_name,
            region=region,
            business=business,
            availability=availability,
            network=network,
            kubernetes=kubernetes,
            database=database,
        )
        return requirement, notes

    def _extract_region(self, lower: str, region_hint: str | None, notes: list[Assumption]) -> Region:
        if region_hint:
            try:
                return Region(region_hint)
            except ValueError:
                pass
        for keyword, region in _REGION_KEYWORDS:
            if keyword in lower:
                notes.append(Assumption(
                    field="region", requested_value="(extracted from free text)", used_value=region.value,
                    reason=f"Detected the phrase '{keyword.strip()}' in the provided text.",
                    strategy_applied="nlp_extraction",
                ))
                return region
        notes.append(Assumption(
            field="region", requested_value="(not mentioned in text)", used_value=Region.US_CENTRAL1.value,
            reason="No region or location was mentioned in the text; defaulted to us-central1.",
            strategy_applied="nlp_extraction",
        ))
        return Region.US_CENTRAL1

    def _extract_business_context(self, lower: str, original_text: str, notes: list[Assumption]) -> BusinessContext:
        peak = None
        total = None
        for number_str, concurrent_flag in _USER_COUNT_RE.findall(lower):
            n = int(number_str.replace(",", ""))
            if concurrent_flag:
                peak = n
            else:
                total = n
        if peak is None and total is not None:
            peak = total
        if total is None and peak is not None:
            total = peak

        if total is not None:
            notes.append(Assumption(
                field="business.total_users", requested_value="(extracted from free text)", used_value=str(total),
                reason="Detected a user-count figure in the provided text.", strategy_applied="nlp_extraction",
            ))
        if peak is not None:
            notes.append(Assumption(
                field="business.peak_concurrent_users", requested_value="(extracted from free text)", used_value=str(peak),
                reason="Detected a concurrent-user figure in the provided text.", strategy_applied="nlp_extraction",
            ))

        return BusinessContext(total_users=total, peak_concurrent_users=peak, notes=original_text.strip()[:1000] or None)

    def _extract_availability(self, lower: str, notes: list[Assumption]) -> AvailabilityRequirement | None:
        ha_detected = any(kw in lower for kw in _HA_KEYWORDS)
        dr_detected = any(kw in lower for kw in _DR_KEYWORDS)

        uptime = None
        m = _UPTIME_RE.search(lower)
        if m:
            uptime = float(m.group(1) or m.group(2))
            notes.append(Assumption(
                field="availability.target_uptime_percent", requested_value="(extracted from free text)",
                used_value=str(uptime), reason=f"Detected an uptime/SLA figure of {uptime}% in the provided text.",
                strategy_applied="nlp_extraction",
            ))

        if not (ha_detected or dr_detected or uptime is not None):
            return None

        if ha_detected:
            notes.append(Assumption(
                field="availability.high_availability", requested_value="(extracted from free text)", used_value="true",
                reason="Detected a high-availability keyword (e.g. 'high availability', 'multi-zone') in the provided text.",
                strategy_applied="nlp_extraction",
            ))
        if dr_detected:
            notes.append(Assumption(
                field="availability.disaster_recovery_required", requested_value="(extracted from free text)", used_value="true",
                reason="Detected a disaster-recovery keyword in the provided text.", strategy_applied="nlp_extraction",
            ))

        return AvailabilityRequirement(
            high_availability=ha_detected or (uptime is not None and uptime >= 99.9),
            target_uptime_percent=uptime,
            disaster_recovery_required=dr_detected,
            backup_frequency=BackupFrequency.DAILY if dr_detected else BackupFrequency.NONE,
        )

    def _extract_network(self, lower: str, notes: list[Assumption]) -> NetworkRequirement | None:
        lb = any(kw in lower for kw in _LB_KEYWORDS)
        cdn = any(kw in lower for kw in _CDN_KEYWORDS)
        vpn = any(kw in lower for kw in _VPN_KEYWORDS)
        egress = None
        m = _EGRESS_RE.search(lower)
        if m:
            value = float(m.group(1))
            egress = value * 1000 if m.group(2).lower() == "tb" else value
            notes.append(Assumption(
                field="network.estimated_egress_gb_per_month", requested_value="(extracted from free text)",
                used_value=str(egress), reason=f"Detected a bandwidth/egress figure ('{m.group(0).strip()}') in the provided text.",
                strategy_applied="nlp_extraction",
            ))

        if not (lb or cdn or vpn or egress):
            return None

        if lb:
            notes.append(Assumption(
                field="network.load_balancer_required", requested_value="(extracted from free text)", used_value="true",
                reason="Detected a load-balancing/high-traffic keyword in the provided text.", strategy_applied="nlp_extraction",
            ))
        if cdn:
            notes.append(Assumption(
                field="network.cdn_enabled", requested_value="(extracted from free text)", used_value="true",
                reason="Detected a CDN/content-delivery keyword in the provided text.", strategy_applied="nlp_extraction",
            ))

        return NetworkRequirement(
            load_balancer_required=lb,
            external_ip_count=1 if lb else 0,
            estimated_egress_gb_per_month=egress or 0,
            cdn_enabled=cdn,
            vpn_required=vpn,
        )

    def _extract_kubernetes(self, lower: str, notes: list[Assumption]) -> KubernetesRequirement | None:
        if not any(kw in lower for kw in _K8S_KEYWORDS):
            return None
        notes.append(Assumption(
            field="kubernetes.required", requested_value="(extracted from free text)", used_value="true",
            reason="Detected a container-orchestration keyword (e.g. 'Kubernetes', 'microservices') in the provided text.",
            strategy_applied="nlp_extraction",
        ))
        return KubernetesRequirement(required=True, autopilot=True)

    def _extract_database(self, lower: str, notes: list[Assumption]) -> DatabaseRequirement | None:
        m = _DB_SIZE_RE.search(lower)
        if not m:
            return None
        size_gb = int(m.group(1))
        notes.append(Assumption(
            field="database.size_gb", requested_value="(extracted from free text)", used_value=str(size_gb),
            reason=f"Detected a database size figure ('{m.group(0).strip()}') in the provided text.",
            strategy_applied="nlp_extraction",
        ))
        return DatabaseRequirement(required=True, engine=CloudSqlEngine.POSTGRES, size_gb=size_gb)

    def _note_gpu_workload(self, lower: str, notes: list[Assumption]) -> None:
        if any(kw in lower for kw in _GPU_KEYWORDS):
            notes.append(Assumption(
                field="compute.gpu_type", requested_value="(extracted from free text)",
                used_value="not automatically provisioned",
                reason=(
                    "Detected a GPU/ML workload keyword in the provided text. GPU-enabled compute is not yet "
                    "auto-provisioned from natural language - manually add a `compute` block with a GPU-compatible "
                    "machine family (e.g. a2) and gpu_type before requesting an estimate."
                ),
                strategy_applied="nlp_extraction",
            ))
