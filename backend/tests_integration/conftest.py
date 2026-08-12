"""Live-server fixture for the integration suite: launches a real `uvicorn`
subprocess and talks to it over real HTTP (httpx), as opposed to
`backend/tests/conftest.py`'s in-process Starlette TestClient. See
tests_integration/README.md for why these are kept separate from the main
suite."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, proc: subprocess.Popen, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"Server process exited early (code {proc.returncode}).\nOutput:\n{output}")
        try:
            # trust_env=False: this sandbox sets a SOCKS proxy for external
            # network egress allowlisting - localhost traffic to our own
            # subprocess must never be routed through it.
            resp = httpx.get(f"{base_url}/health", timeout=1.0, trust_env=False)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.25)
    proc.terminate()
    raise TimeoutError(f"Server never became healthy within {timeout_seconds}s (last error: {last_error}).")


def _spawn_server(database_url: str, tmp_path: Path) -> tuple[subprocess.Popen, str]:
    port = _free_port()
    env = os.environ.copy()
    env.update({
        "FINOPS_DATABASE_URL": database_url,
        "FINOPS_AUTO_CREATE_TABLES": "true",
        "FINOPS_ENVIRONMENT": "development",
        "FINOPS_JWT_SECRET_KEY": "integration-test-secret-key-that-is-at-least-32-chars",
        "FINOPS_RATE_LIMIT_ENABLED": "false",
        "FINOPS_REQUEST_LOGGING_ENABLED": "false",
        "FINOPS_BCRYPT_ROUNDS": "4",
        # Real subprocess, no external broker available - run Celery tasks
        # synchronously in-process, same as the main suite (tests/conftest.py).
        "FINOPS_CELERY_TASK_ALWAYS_EAGER": "true",
        "FINOPS_CELERY_RESULT_BACKEND": "cache+memory://",
        "FINOPS_PRICING_PROVIDER": "mock",
        "FINOPS_CLOUD_PROVIDER": "gcp",
    })
    log_file = open(tmp_path / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND_DIR), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    _wait_for_health(base_url, proc)
    return proc, base_url


@pytest.fixture
def live_server(tmp_path):
    """SQLite-backed live server - always runs (no external dependency)."""
    db_path = tmp_path / "integration.db"
    proc, base_url = _spawn_server(f"sqlite:///{db_path}", tmp_path)
    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def live_server_postgres(tmp_path):
    """Postgres-backed live server - skipped unless FINOPS_TEST_POSTGRES_URL
    is set (see tests_integration/README.md). This sandbox has no
    Docker/Postgres access, so this always skips here; the CI
    `integration-tests` job sets the variable against a real Postgres
    service container."""
    url = os.environ.get("FINOPS_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("FINOPS_TEST_POSTGRES_URL not set - see tests_integration/README.md")
    proc, base_url = _spawn_server(url, tmp_path)
    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
