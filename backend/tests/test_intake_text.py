"""Tests for the natural-language requirement extractor (Phase 4)."""
from app.intake.text_extractor import NaturalLanguageRequirementExtractor


def test_master_prompt_example_extracts_all_signals():
    """The exact scenario from the platform spec: '500 users, HA Required,
    99.99% uptime, 100GB Database' should produce a fully-formed business
    context, availability block, and database hint."""
    text = (
        "We have about 500 users, with roughly 500 peak concurrent users. "
        "High availability is required with 99.99% uptime. We need a 100GB database. "
        "Also need disaster recovery."
    )
    req, notes = NaturalLanguageRequirementExtractor().extract("New Customer Portal", text)

    assert req.business.total_users == 500
    assert req.business.peak_concurrent_users == 500
    assert req.availability.high_availability is True
    assert req.availability.target_uptime_percent == 99.99
    assert req.availability.disaster_recovery_required is True
    assert req.database.required is True
    assert req.database.size_gb == 100
    assert req.database.high_availability is True  # cross-linked from overall HA
    assert len(notes) >= 5
    assert all(n.strategy_applied == "nlp_extraction" for n in notes)


def test_region_detection_from_location_keyword():
    req, notes = NaturalLanguageRequirementExtractor().extract("Mumbai App", "Our users are mostly in Mumbai, India.")
    assert req.region.value == "asia-south1"
    assert any(n.field == "region" for n in notes)


def test_region_hint_overrides_text_detection():
    req, _ = NaturalLanguageRequirementExtractor().extract(
        "Test", "Our users are in Mumbai.", region_hint="europe-west1",
    )
    assert req.region.value == "europe-west1"


def test_no_signals_produces_minimal_requirement_without_crashing():
    req, notes = NaturalLanguageRequirementExtractor().extract("Empty Project", "Please build something for us.")
    assert req.project_name == "Empty Project"
    assert req.business.total_users is None
    assert req.availability is None
    assert req.network is None
    assert req.kubernetes is None
    assert req.database is None
    # Still logs the region default as a transparent assumption.
    assert any(n.field == "region" for n in notes)


def test_kubernetes_keyword_detection():
    req, notes = NaturalLanguageRequirementExtractor().extract(
        "Microservices App", "We're running a microservices architecture on Kubernetes with many containers.",
    )
    assert req.kubernetes is not None
    assert req.kubernetes.required is True
    assert req.kubernetes.autopilot is True


def test_load_balancer_and_cdn_detection():
    req, notes = NaturalLanguageRequirementExtractor().extract(
        "High Traffic Site", "We expect high traffic and need a CDN for static asset caching plus a load balancer.",
    )
    assert req.network is not None
    assert req.network.load_balancer_required is True
    assert req.network.cdn_enabled is True


def test_gpu_workload_produces_note_but_no_auto_provisioned_compute():
    req, notes = NaturalLanguageRequirementExtractor().extract(
        "ML Training Cluster", "We need to run deep learning model training with GPUs.",
    )
    assert req.compute is None  # GPU compute is never auto-provisioned from text
    assert any(n.field == "compute.gpu_type" for n in notes)


def test_egress_bandwidth_detection_with_tb_conversion():
    req, notes = NaturalLanguageRequirementExtractor().extract(
        "Media Site", "We serve roughly 2TB of egress traffic per month with high traffic patterns.",
    )
    assert req.network is not None
    assert req.network.estimated_egress_gb_per_month == 2000
