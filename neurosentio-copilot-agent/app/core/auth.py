"""
Authentication dependency for NeuroSentio Copilot Agent.

Supports two verification strategies:
  1. HS256 using SUPABASE_JWT_SECRET (current, fastest path)
  2. JWKS/asymmetric using SUPABASE_JWKS_URL (future, documented placeholder)

Behavior matrix:
  ┌──────────────────┬──────────────────────────┬──────────────────────┐
  │ Mode             │ X-User-ID                │ Bearer JWT           │
  ├──────────────────┼──────────────────────────┼──────────────────────┤
  │ development      │ ✅ (if allowed)          │ ✅ (if configured)   │
  │ production       │ ❌ rejected / ignored    │ ✅ required          │
  └──────────────────┴──────────────────────────┴──────────────────────┘

Privacy: JWT payloads are never logged. Only the "sub" claim is extracted.
"""

import logging
from typing import Optional

import jwt
from fastapi import Request, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── JWT verification strategies ────────────────────────────────────────


class JWTVerificationError(Exception):
    """Raised when JWT verification fails."""
    pass


def _verify_jwt_hs256(token: str, secret: str, audience: Optional[str]) -> dict:
    """
    Verify a JWT using HS256 symmetric secret.
    This is the standard path for Supabase Auth when using the project JWT secret.
    """
    decode_options = {}
    kwargs = {
        "algorithms": ["HS256"],
        "options": decode_options,
    }
    if audience:
        kwargs["audience"] = audience

    try:
        payload = jwt.decode(token, secret, **kwargs)
        return payload
    except jwt.ExpiredSignatureError:
        raise JWTVerificationError("Token has expired")
    except jwt.InvalidAudienceError:
        raise JWTVerificationError("Invalid token audience")
    except jwt.InvalidTokenError as e:
        raise JWTVerificationError(f"Invalid token: {e}")


def _verify_jwt_jwks(token: str, jwks_url: str, audience: Optional[str]) -> dict:
    """
    Verify a JWT using JWKS (asymmetric keys — RS256/ES256).

    Uses PyJWT's built-in PyJWKClient which fetches and caches
    the public keys from the Supabase JWKS endpoint automatically.
    """
    try:
        jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        kwargs = {
            "algorithms": ["RS256", "ES256"],
        }
        if audience:
            kwargs["audience"] = audience

        payload = jwt.decode(token, signing_key.key, **kwargs)
        return payload
    except jwt.ExpiredSignatureError:
        raise JWTVerificationError("Token has expired")
    except jwt.InvalidAudienceError:
        raise JWTVerificationError("Invalid token audience")
    except jwt.PyJWKClientError as e:
        raise JWTVerificationError(f"JWKS key fetch failed: {e}")
    except jwt.InvalidTokenError as e:
        raise JWTVerificationError(f"Invalid token: {e}")


def _verify_token(token: str) -> dict:
    """
    Route to the correct verification strategy based on configuration.

    Priority:
    1. SUPABASE_JWKS_URL → asymmetric (RS256/ES256) — future
    2. SUPABASE_JWT_SECRET → symmetric (HS256) — current
    3. Neither configured → raise error
    """
    settings = get_settings()
    audience = settings.supabase_jwt_audience or None

    if settings.supabase_jwks_url:
        return _verify_jwt_jwks(token, settings.supabase_jwks_url, audience)

    if settings.supabase_jwt_secret:
        return _verify_jwt_hs256(token, settings.supabase_jwt_secret, audience)

    raise JWTVerificationError(
        "No JWT verification method configured. "
        "Set SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL in your .env file."
    )


# ── FastAPI dependency ─────────────────────────────────────────────────


def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency that extracts the authenticated user_id.

    Development mode (APP_ENV=development, ALLOW_DEV_USER_HEADER=true):
      - Accepts X-User-ID header for convenience
      - Falls back to configured default_user_id ("demo-user")
      - Also accepts Bearer JWT if present (takes priority)

    Production mode (APP_ENV=production or AUTH_REQUIRED=true):
      - Requires Authorization: Bearer <jwt>
      - Rejects X-User-ID header alone
      - Returns 401 for missing, invalid, or expired tokens

    Returns:
      str: The authenticated user_id (from JWT 'sub' claim or dev header)

    Raises:
      HTTPException(401): When authentication fails in production mode
    """
    settings = get_settings()

    is_production = settings.is_production or settings.auth_required
    allow_dev_header = settings.allow_dev_user_header and not is_production

    # ── Try Bearer token first (works in both modes) ──────────────────
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            try:
                payload = _verify_token(token)
                sub = payload.get("sub")
                if not sub:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token: missing 'sub' claim",
                    )
                return str(sub)
            except JWTVerificationError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid or expired token",
                )

    # ── Development mode: allow X-User-ID ─────────────────────────────
    if allow_dev_header:
        dev_user_id = request.headers.get(settings.user_id_header)
        return dev_user_id or settings.default_user_id

    # ── Production mode: no valid token → 401 ─────────────────────────
    if is_production:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # ── Fallback for non-production without dev header ────────────────
    # This covers edge cases like APP_ENV=testing with AUTH_REQUIRED=false
    dev_user_id = request.headers.get(settings.user_id_header)
    return dev_user_id or settings.default_user_id
