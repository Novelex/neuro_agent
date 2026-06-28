"""
E2E Auth Verification Script.

Simulates both development and production mode scenarios.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import time
import requests
import jwt as pyjwt

BASE_URL = "http://127.0.0.1:8000"
TEST_JWT_SECRET = None


def _create_test_jwt(sub, secret, exp_offset=3600):
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "role": "authenticated",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _check(label, resp, expected_status):
    status_ok = resp.status_code == expected_status
    icon = "[PASS]" if status_ok else "[FAIL]"
    print(f"  {icon} {label}: {resp.status_code} (expected {expected_status})")
    if not status_ok:
        print(f"     Response: {resp.text[:200]}")
    return status_ok


def run_dev_mode_tests():
    print("\n" + "=" * 60)
    print("DEVELOPMENT MODE TESTS")
    print("=" * 60)
    results = []

    r = requests.get(f"{BASE_URL}/health")
    results.append(_check("GET /health (no auth)", r, 200))

    r = requests.get(f"{BASE_URL}/profile", headers={"X-User-ID": "e2e-dev-user"})
    results.append(_check("GET /profile (X-User-ID)", r, 200))
    if r.status_code == 200:
        uid = r.json()["user_id"]
        assert uid == "e2e-dev-user", f"Expected e2e-dev-user, got {uid}"
        print(f"     user_id = {uid}")

    r = requests.post(
        f"{BASE_URL}/tasks",
        json={"title": "E2E dev test task"},
        headers={"X-User-ID": "e2e-dev-user"},
    )
    results.append(_check("POST /tasks (X-User-ID)", r, 201))

    r = requests.get(f"{BASE_URL}/copilot/dashboard", headers={"X-User-ID": "e2e-dev-user"})
    results.append(_check("GET /copilot/dashboard (X-User-ID)", r, 200))

    passed = sum(results)
    total = len(results)
    print(f"\n  Dev mode: {passed}/{total} passed")
    return passed == total


def run_production_mode_tests(jwt_secret):
    print("\n" + "=" * 60)
    print("PRODUCTION MODE TESTS")
    print("=" * 60)
    results = []

    r = requests.get(f"{BASE_URL}/health")
    results.append(_check("GET /health (no auth) -> 200", r, 200))

    r = requests.get(f"{BASE_URL}/profile")
    results.append(_check("GET /profile (no auth) -> 401", r, 401))

    r = requests.get(f"{BASE_URL}/profile", headers={"X-User-ID": "spoofed-user"})
    results.append(_check("GET /profile (X-User-ID only) -> 401", r, 401))

    r = requests.get(f"{BASE_URL}/profile", headers={"Authorization": "Bearer invalid-token"})
    results.append(_check("GET /profile (invalid token) -> 401", r, 401))

    token = _create_test_jwt("e2e-prod-user", jwt_secret)
    r = requests.get(f"{BASE_URL}/profile", headers={"Authorization": f"Bearer {token}"})
    results.append(_check("GET /profile (valid JWT) -> 200", r, 200))
    if r.status_code == 200:
        uid = r.json()["user_id"]
        assert uid == "e2e-prod-user", f"Expected e2e-prod-user, got {uid}"
        print(f"     user_id = {uid}")

    expired_token = _create_test_jwt("expired-user", jwt_secret, exp_offset=-3600)
    r = requests.get(f"{BASE_URL}/profile", headers={"Authorization": f"Bearer {expired_token}"})
    results.append(_check("GET /profile (expired JWT) -> 401", r, 401))

    passed = sum(results)
    total = len(results)
    print(f"\n  Production mode: {passed}/{total} passed")
    return passed == total


def main():
    import os
    global TEST_JWT_SECRET
    TEST_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "test-jwt-secret-for-e2e")

    print("NeuroSentio Copilot Agent -- E2E Auth Verification")
    print(f"Target: {BASE_URL}")

    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
    except requests.ConnectionError:
        print(f"\n[FAIL] Server not reachable at {BASE_URL}")
        print("   Start the server first: uvicorn app.main:app --reload")
        sys.exit(1)

    mode = "unknown"
    try:
        r = requests.get(f"{BASE_URL}/profile")
        mode = "production" if r.status_code == 401 else "development"
    except Exception:
        pass

    print(f"Detected mode: {mode}")

    if mode == "development":
        success = run_dev_mode_tests()
    else:
        success = run_production_mode_tests(TEST_JWT_SECRET)

    print("\n" + "=" * 60)
    if success:
        print("All E2E tests passed!")
    else:
        print("Some E2E tests failed. Review output above.")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
