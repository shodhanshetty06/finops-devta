"""
Regression tests for arbitrary-layout Excel intake (ExtractionService,
app/services/extraction_service.py) - the Groq-assisted fallback used when
a customer's workbook doesn't match the platform's own questionnaire
template at all.

Covers the hard guarantees from the feature spec:
- an arbitrary customer layout (different sheet/column names) can still be
  parsed into a priced requirement
- Groq extraction only ever produces a *requirement* (never a price - the
  schema has no price fields, so this is structurally enforced, not just
  prompted for)
- a resource Groq isn't confident about is flagged for review, never
  silently hallucinated
- Groq being unavailable, erroring, or returning garbage degrades
  gracefully to a clear "could not be understood" result and never raises
  past the API, so deterministic pricing is simply skipped, not broken
- the platform's own template is always preferred and never touches Groq
"""
import io
import json

import httpx
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.dependencies import get_estimation_service
from app.intake.excel_parser import ExcelQuestionnaireParser
from app.llm.groq_provider import GroqProvider
from app.main import app
from app.services.extraction_service import UNMAPPABLE_MESSAGE, ExtractionService, get_extraction_service

client = TestClient(app)


def _arbitrary_workbook_bytes() -> bytes:
    """A layout that shares none of the template's exact labels - different
    sheet name, different headers, values in different columns - the kind
    of "any customer Excel" the feature is meant to handle."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Server Specs"
    ws.append(["Item", "Detail"])
    ws.append(["Client", "Acme Logistics"])
    ws.append(["No. of Cores", 8])
    ws.append(["Memory (GB)", 32])
    ws.append(["Volume (GB)", 250])
    ws.append(["Cloud SQL Needed", "Yes"])
    ws.append(["Weird internal note", "purge cache nightly"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mock_extraction_transport(response_body: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response_body)}}]})
    return httpx.MockTransport(handler)


_GOOD_EXTRACTION_RESPONSE = {
    "project_name": "Acme Logistics",
    "region_hint": None,
    "compute": {"vcpu": 8, "ram_gb": 32, "machine_family": None, "instance_count": None, "gpu_type": None, "gpu_count": None},
    "storage": {"size_gb": 250, "disk_type": None, "snapshot_enabled": None, "snapshot_retention_days": None},
    "database": {"required": True, "engine": None, "size_gb": None, "vcpu": None, "ram_gb": None, "high_availability": None},
    "network": None, "kubernetes": None, "availability": None, "business": None,
    "assumptions": [
        {"field": "compute.vcpu", "requested_value": "8 Cores", "used_value": "8", "reason": "'Cores' means vCPU count."},
    ],
    "unmapped": [
        {"sheet": "Server Specs", "label": "Weird internal note", "value": "purge cache nightly", "reason": "Not a recognizable infrastructure requirement."},
    ],
}


# -- Template always wins first, no Groq call ------------------------------

def test_template_layout_never_calls_groq():
    class _ExplodingProvider:
        def complete_json(self, *, system_prompt, user_prompt):
            raise AssertionError("Groq must not be called when the template parser already recognized the workbook")

    from app.intake.excel_template import ExcelTemplateGenerator
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(ExcelTemplateGenerator().generate()))
    ws = wb["Questionnaire"]
    for row in ws.iter_rows():
        if row[0].value == "vCPU":
            row[1].value = 4
        if row[0].value == "RAM (GB)":
            row[1].value = 16
    buf = io.BytesIO()
    wb.save(buf)

    service = ExtractionService(provider=_ExplodingProvider(), model="x")
    requirement, issues, notes, source = service.extract(buf.getvalue())
    assert source == "template"
    assert requirement.compute.vcpu == 4
    assert notes == []


# -- Arbitrary layout, Groq available and confident -------------------------

def test_arbitrary_layout_extracted_via_groq():
    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=_mock_extraction_transport(_GOOD_EXTRACTION_RESPONSE))
    service = ExtractionService(provider=provider, model="llama-3.1-8b-instant")

    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    assert source == "ai"
    assert requirement is not None
    assert requirement.project_name == "Acme Logistics"
    assert requirement.compute.vcpu == 8
    assert requirement.compute.ram_gb == 32
    assert requirement.storage.size_gb == 250
    assert requirement.database.required is True

    # The synonym mapping ("Cores" -> vcpu) is recorded as an assumption, not silently applied.
    assert any(a.field == "compute.vcpu" and "8 Cores" in a.requested_value for a in notes)
    assert all(a.strategy_applied == "ai_extraction" for a in notes)

    # The row Groq couldn't confidently map is flagged for review, not dropped or hallucinated into a section.
    warning_issues = [i for i in issues if i.severity.value == "warning"]
    assert any("Weird internal note" in i.field for i in warning_issues)


def test_arbitrary_layout_auto_estimate_prices_only_the_extracted_data():
    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=_mock_extraction_transport(_GOOD_EXTRACTION_RESPONSE))
    app.dependency_overrides[get_extraction_service] = lambda: ExtractionService(provider=provider, model="x")
    try:
        resp = client.post(
            "/api/v1/intake/excel?auto_estimate=true",
            files={"file": ("acme.xlsx", _arbitrary_workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    finally:
        app.dependency_overrides.pop(get_extraction_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_source"] == "ai"
    assert body["requirement"]["compute"]["vcpu"] == 8
    assert body["estimate"] is not None
    assert body["estimate"]["cost"]["total_monthly"] > 0


# -- Groq cannot invent a price, even if it tries ----------------------------

def test_groq_price_injection_attempt_is_ignored_by_schema(catalog, pricing_provider, settings):
    """Even if a (malicious or confused) Groq response includes price-like
    fields, CustomerRequirement has no such fields to receive them - the
    only number in the final estimate is whatever the real deterministic
    PricingEngine computes from the extracted resource spec, never
    anything Groq sent."""
    from app.services.estimation_service import EstimationService

    injected = dict(_GOOD_EXTRACTION_RESPONSE)
    injected["compute"] = dict(injected["compute"])
    injected["compute"]["price_per_month"] = 999999  # not a real field
    injected["total_price"] = 1  # top-level, also not a real field
    injected["sku"] = "FAKE-SKU-1"

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=_mock_extraction_transport(injected))
    service = ExtractionService(provider=provider, model="llama-3.1-8b-instant")
    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    assert requirement is not None
    assert not hasattr(requirement, "price_per_month")
    assert not hasattr(requirement, "total_price")
    assert not hasattr(requirement, "sku")

    estimate = EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings).generate_estimate(requirement)
    assert estimate.cost.total_monthly not in (999999, 1)
    assert estimate.cost.total_monthly > 0


# -- Ambiguous/unresolvable section is flagged, never hallucinated ----------

def test_partially_invalid_section_is_flagged_not_hallucinated():
    bad = dict(_GOOD_EXTRACTION_RESPONSE)
    bad["compute"] = {"vcpu": "a lot", "ram_gb": 32, "machine_family": None, "instance_count": None, "gpu_type": None, "gpu_count": None}

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=_mock_extraction_transport(bad))
    service = ExtractionService(provider=provider, model="llama-3.1-8b-instant")
    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    # vcpu could not be interpreted -> flagged as a warning, compute.vcpu never guessed at.
    assert any("vCPU" in i.field and i.severity.value == "warning" for i in issues)
    # ram_gb alone doesn't satisfy ComputeRequirement (vcpu is required), so the whole section
    # is dropped rather than priced on a half-guessed configuration.
    assert requirement.compute is None
    # storage/database still came through fine - one bad field never blocks the rest.
    assert requirement.storage.size_gb == 250


# -- Graceful fallback: Groq unavailable / erroring / garbage --------------

def test_groq_unconfigured_returns_clear_review_message_not_a_crash():
    service = ExtractionService(provider=None, model=None)
    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    assert requirement is None
    assert source == "unrecognized"
    assert any(i.message == UNMAPPABLE_MESSAGE for i in issues)


def test_groq_api_failure_falls_back_gracefully():
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(failing_handler))
    service = ExtractionService(provider=provider, model="llama-3.1-8b-instant")
    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    assert requirement is None
    assert source == "unrecognized"
    assert any(i.severity.value == "blocker" for i in issues)


def test_groq_garbage_response_falls_back_gracefully():
    def garbage_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]})

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(garbage_handler))
    service = ExtractionService(provider=provider, model="llama-3.1-8b-instant")
    requirement, issues, notes, source = service.extract(_arbitrary_workbook_bytes())

    assert requirement is None
    assert source == "unrecognized"


def test_api_endpoint_never_500s_when_groq_is_unconfigured(monkeypatch):
    # conftest.py forces GROQ_API_KEY="" for the whole suite, so the default
    # TestClient wiring already exercises "Groq not configured" - this just
    # confirms the endpoint itself degrades to a clean 200, not a crash.
    resp = client.post(
        "/api/v1/intake/excel?auto_estimate=true",
        files={"file": ("acme.xlsx", _arbitrary_workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requirement"] is None
    assert body["estimate"] is None
    assert body["extraction_source"] == "unrecognized"
    assert any(i["message"] == UNMAPPABLE_MESSAGE for i in body["issues"])


# -- No leakage between an unrelated prior estimation service call ---------

def test_extraction_is_independent_of_estimation_service_dependency(catalog, pricing_provider, settings):
    """Overriding get_estimation_service (as other tests do) must not
    change extraction behavior - the two are unrelated dependencies."""
    from app.services.estimation_service import EstimationService

    app.dependency_overrides[get_estimation_service] = lambda: EstimationService(catalog=catalog, pricing_provider=pricing_provider, settings=settings)
    try:
        resp = client.post(
            "/api/v1/intake/excel",
            files={"file": ("acme.xlsx", _arbitrary_workbook_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    finally:
        app.dependency_overrides.pop(get_estimation_service, None)
    assert resp.status_code == 200
    assert resp.json()["extraction_source"] == "unrecognized"  # still no Groq configured
