"""Tests for the structured request logging middleware."""
import json
import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_response_includes_request_id_header():
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers
    # Looks like a UUID4 (36 chars, hyphens in the right places) - not
    # asserting exact format via regex, just the shape a UUID always has.
    request_id = resp.headers["X-Request-ID"]
    assert len(request_id) == 36
    assert request_id.count("-") == 4


def test_each_request_gets_a_distinct_request_id():
    id_a = client.get("/health").headers["X-Request-ID"]
    id_b = client.get("/health").headers["X-Request-ID"]
    assert id_a != id_b


def test_logs_a_structured_json_line_per_request(caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/api/v1/catalog/regions")
    request_id = resp.headers["X-Request-ID"]

    matching = [r for r in caplog.records if r.name == "app.access"]
    assert len(matching) >= 1
    payload = json.loads(matching[-1].message)
    assert payload["request_id"] == request_id
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/catalog/regions"
    assert payload["status_code"] == 200
    assert isinstance(payload["duration_ms"], (int, float))
    assert payload["duration_ms"] >= 0


def test_logs_the_actual_status_code_on_error_responses(caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/api/v1/projects")  # requires auth -> 401
    assert resp.status_code == 401

    matching = [r for r in caplog.records if r.name == "app.access"]
    payload = json.loads(matching[-1].message)
    assert payload["status_code"] == 401
