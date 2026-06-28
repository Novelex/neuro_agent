"""
Auth tests (Part F).

Tests cover:
1. Dev mode allows X-User-ID
2. Dev mode defaults demo-user if no header
3. Production rejects missing token
4. Production rejects X-User-ID only
5. Invalid Bearer token rejected
6. Valid JWT extracts sub
7. Expired JWT rejected
8. Health stays public without auth
9. Cross-user access still blocked
"""

import time
import pytest
import jwt as pyjwt
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import Settings

# ── Test DB ─────────────────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Test JWT secret — never used in production
TEST_JWT_SECRET = "test-jwt-secret-for-neurosentio-auth-tests-only"


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app)


def _make_dev_settings(**overrides):
    """Create development-mode settings."""
    defaults = {
        "app_env": "development",
        "allow_dev_user_header": True,
        "auth_required": False,
        "supabase_jwt_secret": TEST_JWT_SECRET,
        "supabase_jwt_audience": "authenticated",
        "database_url": TEST_DB_URL,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_prod_settings(**overrides):
    """Create production-mode settings."""
    defaults = {
        "app_env": "production",
        "allow_dev_user_header": False,
        "auth_required": True,
        "supabase_jwt_secret": TEST_JWT_SECRET,
        "supabase_jwt_audience": "authenticated",
        "database_url": TEST_DB_URL,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _create_test_jwt(sub: str, secret: str = TEST_JWT_SECRET, exp_offset: int = 3600, **extra_claims) -> str:
    """Create a test JWT token."""
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "role": "authenticated",
    }
    payload.update(extra_claims)
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ══════════════════════════════════════════════════════════════════════
# TEST 1: Dev mode allows X-User-ID
# ══════════════════════════════════════════════════════════════════════

def test_dev_mode_allows_x_user_id():
    """In development mode with ALLOW_DEV_USER_HEADER=true, X-User-ID should work."""
    with patch("app.core.auth.get_settings", return_value=_make_dev_settings()):
        resp = client.get(
            "/profile",
            headers={"X-User-ID": "auth-dev-test-user"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "auth-dev-test-user"


# ══════════════════════════════════════════════════════════════════════
# TEST 2: Dev mode defaults demo-user if no header
# ══════════════════════════════════════════════════════════════════════

def test_dev_mode_defaults_demo_user_if_allowed():
    """In development mode with no X-User-ID, default to demo-user."""
    with patch("app.core.auth.get_settings", return_value=_make_dev_settings()):
        resp = client.get("/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-user"


# ══════════════════════════════════════════════════════════════════════
# TEST 3: Production rejects missing token
# ══════════════════════════════════════════════════════════════════════

def test_production_rejects_missing_token():
    """In production mode, missing Authorization header returns 401."""
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get("/profile")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
# TEST 4: Production rejects X-User-ID only
# ══════════════════════════════════════════════════════════════════════

def test_production_rejects_x_user_id_only():
    """In production mode, X-User-ID alone is not accepted."""
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get(
            "/profile",
            headers={"X-User-ID": "spoofed-user"},
        )
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
# TEST 5: Invalid Bearer token rejected
# ══════════════════════════════════════════════════════════════════════

def test_invalid_bearer_token_rejected():
    """An invalid Bearer token returns 401."""
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get(
            "/profile",
            headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
        )
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
# TEST 6: Valid JWT extracts sub
# ══════════════════════════════════════════════════════════════════════

def test_valid_jwt_extracts_sub():
    """A valid JWT's 'sub' claim becomes the user_id."""
    token = _create_test_jwt(sub="jwt-user-abc123")
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get(
            "/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "jwt-user-abc123"


# ══════════════════════════════════════════════════════════════════════
# TEST 7: Expired JWT rejected
# ══════════════════════════════════════════════════════════════════════

def test_expired_jwt_rejected():
    """An expired JWT returns 401."""
    token = _create_test_jwt(sub="expired-user", exp_offset=-3600)
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get(
            "/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
# TEST 8: Health stays public
# ══════════════════════════════════════════════════════════════════════

def test_health_public_without_auth():
    """GET /health works without any authentication even in production mode."""
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ══════════════════════════════════════════════════════════════════════
# TEST 9: Cross-user access still blocked
# ══════════════════════════════════════════════════════════════════════

def test_cross_user_access_still_blocked():
    """User A creates a task; User B's JWT should not access it."""
    # Create task as user A
    token_a = _create_test_jwt(sub="cross-user-a")
    token_b = _create_test_jwt(sub="cross-user-b")

    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        # User A creates a task
        create_resp = client.post(
            "/tasks",
            json={"title": "User A private task", "status": "open"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # User B tries to access User A's task list — should not see User A's tasks
        list_resp = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert list_resp.status_code == 200
        task_ids = [t["id"] for t in list_resp.json()]
        assert task_id not in task_ids, "User B should not see User A's task"


# ══════════════════════════════════════════════════════════════════════
# BONUS TESTS
# ══════════════════════════════════════════════════════════════════════

def test_wrong_secret_jwt_rejected():
    """A JWT signed with the wrong secret returns 401."""
    token = pyjwt.encode(
        {"sub": "wrong-secret-user", "aud": "authenticated", "exp": int(time.time()) + 3600},
        "completely-wrong-secret",
        algorithm="HS256",
    )
    with patch("app.core.auth.get_settings", return_value=_make_prod_settings()):
        resp = client.get(
            "/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_jwt_takes_priority_over_x_user_id_in_dev():
    """When both JWT and X-User-ID are present in dev mode, JWT wins."""
    token = _create_test_jwt(sub="jwt-priority-user")
    with patch("app.core.auth.get_settings", return_value=_make_dev_settings()):
        resp = client.get(
            "/profile",
            headers={
                "Authorization": f"Bearer {token}",
                "X-User-ID": "should-be-ignored",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "jwt-priority-user"


def test_jwks_url_returns_not_implemented():
    """When SUPABASE_JWKS_URL is configured, auth fails with a clear error."""
    token = _create_test_jwt(sub="jwks-user")
    settings = _make_prod_settings(
        supabase_jwks_url="https://example.supabase.co/.well-known/jwks.json",
        supabase_jwt_secret=None,
    )
    with patch("app.core.auth.get_settings", return_value=settings):
        resp = client.get(
            "/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
    # Should return 401 because JWKS verification is not yet implemented
    assert resp.status_code == 401
