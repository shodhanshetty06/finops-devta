from tests.conftest import register_and_login


def test_register_creates_user_with_default_customer_role(api_client):
    resp = api_client.post("/api/v1/auth/register", json={
        "email": "alice@example.com", "password": "supersecret123", "full_name": "Alice",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "customer"
    assert body["is_active"] is True
    assert "id" in body


def test_register_duplicate_email_returns_409(api_client):
    payload = {"email": "bob@example.com", "password": "supersecret123", "full_name": "Bob"}
    assert api_client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = api_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"] == "duplicate_email"


def test_register_cannot_self_elevate_to_admin(api_client):
    """Regression test: a live QA pass found that POST /api/v1/auth/register
    honored an attacker-supplied role="admin" verbatim, letting any
    unauthenticated caller grant themselves organization-wide read access
    to every user's projects (ProjectService bypasses the ownership check
    entirely for role == "admin"). The public endpoint must reject this."""
    resp = api_client.post("/api/v1/auth/register", json={
        "email": "eve-wannabe-admin@example.com", "password": "supersecret123",
        "full_name": "Eve", "role": "admin",
    })
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"

    # the email must not have been consumed by the rejected attempt - a
    # legitimate follow-up registration with a permitted role should work
    resp2 = api_client.post("/api/v1/auth/register", json={
        "email": "eve-wannabe-admin@example.com", "password": "supersecret123",
        "full_name": "Eve", "role": "customer",
    })
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "customer"


def test_register_self_service_consultant_role_still_allowed(api_client):
    """The consultant role carries no elevated cross-user access (unlike
    admin - see ProjectService), so self-service registration as a
    consultant is intentionally still allowed; only "admin" is blocked."""
    resp = api_client.post("/api/v1/auth/register", json={
        "email": "frank-consultant@example.com", "password": "supersecret123",
        "full_name": "Frank", "role": "consultant",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "consultant"


def test_login_success_returns_bearer_token(api_client):
    api_client.post("/api/v1/auth/register", json={
        "email": "carol@example.com", "password": "supersecret123", "full_name": "Carol",
    })
    resp = api_client.post("/api/v1/auth/login", data={"username": "carol@example.com", "password": "supersecret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_wrong_password_returns_401(api_client):
    api_client.post("/api/v1/auth/register", json={
        "email": "dave@example.com", "password": "supersecret123", "full_name": "Dave",
    })
    resp = api_client.post("/api/v1/auth/login", data={"username": "dave@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_credentials"


def test_me_requires_authentication(api_client):
    resp = api_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(api_client):
    user, headers = register_and_login(api_client, "erin@example.com")
    resp = api_client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "erin@example.com"
    assert resp.json()["id"] == user["id"]


def test_invalid_token_rejected(api_client):
    resp = api_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
