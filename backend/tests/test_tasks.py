"""Tests for the Celery tasks themselves (app/tasks/), run in eager mode
(see conftest.py) - no broker or worker required. Exercises the tasks as
plain functions via `.delay()` / `AsyncResult`, the same interface the
jobs API uses, so these tests double as a check that the tasks' arguments
and return values really do round-trip through JSON (task_serializer="json")
rather than only working by accident in-process."""
import base64

import pytest

from app.domain.branding import BrandingConfig
from app.domain.enums import DiskType, MachineFamily, Region
from app.domain.requirements import ComputeRequirement, CustomerRequirement, StorageRequirement
from app.tasks.batch_tasks import generate_batch_estimates_task
from app.tasks.report_tasks import generate_report_task


def _requirement_json(project_name="Test Project", vcpu=2, ram_gb=8):
    req = CustomerRequirement(
        project_name=project_name,
        region=Region.US_CENTRAL1,
        compute=ComputeRequirement(machine_family=MachineFamily.E2, vcpu=vcpu, ram_gb=ram_gb, instance_count=1),
    )
    return req.model_dump(mode="json")


def test_generate_report_task_excel(sample_estimate):
    async_result = generate_report_task.delay(
        sample_estimate.model_dump(mode="json"), BrandingConfig().model_dump(mode="json"), "excel",
    )
    assert async_result.successful()
    payload = async_result.result
    assert payload["content_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert payload["filename"].endswith(".xlsx")
    file_bytes = base64.b64decode(payload["data_b64"])
    assert file_bytes[:2] == b"PK"  # zip signature - a real xlsx
    assert payload["size_bytes"] == len(file_bytes)


def test_generate_report_task_pdf(sample_estimate):
    async_result = generate_report_task.delay(
        sample_estimate.model_dump(mode="json"), BrandingConfig().model_dump(mode="json"), "pdf",
    )
    assert async_result.successful()
    payload = async_result.result
    assert payload["content_type"] == "application/pdf"
    file_bytes = base64.b64decode(payload["data_b64"])
    assert file_bytes[:5] == b"%PDF-"


def test_generate_report_task_rejects_unknown_format(sample_estimate):
    async_result = generate_report_task.delay(
        sample_estimate.model_dump(mode="json"), BrandingConfig().model_dump(mode="json"), "csv",
    )
    assert async_result.failed()
    assert "csv" in str(async_result.result)


def test_batch_estimate_task_prices_every_item():
    items = [_requirement_json("Project A", vcpu=2, ram_gb=8), _requirement_json("Project B", vcpu=4, ram_gb=16)]
    async_result = generate_batch_estimates_task.delay(items, False, 0)
    assert async_result.successful()
    payload = async_result.result
    assert payload["total"] == 2
    assert payload["succeeded"] == 2
    assert payload["failed"] == 0
    for item in payload["items"]:
        assert item["status"] == "success"
        assert item["result"]["cost"]["total_monthly"] > 0


def test_batch_estimate_task_isolates_bad_items():
    good = _requirement_json("Good Project")
    # A dict-level mutation (not a typed constructor call) is required here:
    # CustomerRequirement's own vcpu_reasonable validator would reject this
    # value immediately if built via the Pydantic model in this test
    # process. Going through a raw dict instead simulates exactly what the
    # task receives over the wire - untrusted, not-yet-validated JSON - and
    # is what actually exercises the task's per-item try/except.
    bad = _requirement_json("Bad Project")
    bad["compute"]["vcpu"] = 99999  # exceeds the vCPU sanity check (max ~416)
    async_result = generate_batch_estimates_task.delay([good, bad], False, 0)
    assert async_result.successful()  # the task itself succeeds even though one item failed
    payload = async_result.result
    assert payload["total"] == 2
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    statuses = {item["project_name"]: item["status"] for item in payload["items"]}
    assert statuses["Good Project"] == "success"
    assert statuses["Bad Project"] == "error"


def test_batch_estimate_task_honors_commitment_term():
    items = [_requirement_json("Committed Project")]
    async_result = generate_batch_estimates_task.delay(items, False, 3)
    result = async_result.result["items"][0]["result"]
    discount_names = [d["name"] for d in result["cost"]["discounts"]]
    assert any("3-Year" in name for name in discount_names)
