"""
Reply Drafter Service (Day 7, hardened Day 9).

Day 9 additions:
- Prompt versioning (from app/prompts/reply_drafting.py)
- Prompt injection safety scan
- Rate limiting check
- LLM usage logging (metadata only — no prompt text, no message text)
- Cost estimation
- Latency tracking

This service NEVER sends messages.
It NEVER creates Gmail drafts or connects external services.
All drafts are stored locally in the SQLite database.
"""

import logging
import time
from typing import Optional, List
from sqlalchemy.orm import Session

from app.llm.base import BaseLLMClient, LLMError
from app.llm.client_factory import get_llm_client
from app.repositories.reply_draft_repository import reply_draft_repository
from app.repositories.user_profile_repository import user_profile_repository
from app.repositories.llm_usage_repository import llm_usage_repository
from app.schemas.reply_schema import (
    ReplyDraft as ReplyDraftSchema,
    ReplyDraftRequest,
    ReplyDraftLLMOutput,
    ReplyDraftOption,
)
from app.prompts import reply_drafting as reply_prompts
from app.utils.prompt_safety import detect_prompt_injection_risk, build_safety_prefix
from app.utils.llm_costs import estimate_llm_cost
from app.services.llm_rate_limit_service import check_rate_limit, log_rate_limit_skip

logger = logging.getLogger(__name__)

# Re-export for backward compatibility (tests import SYSTEM_PROMPT directly)
SYSTEM_PROMPT = reply_prompts.SYSTEM_PROMPT
PROMPT_VERSION = reply_prompts.PROMPT_VERSION


def _build_user_prompt(request: ReplyDraftRequest, profile_tone: Optional[str]) -> str:
    return reply_prompts.build_user_prompt(
        original_message=request.original_message,
        message_sender=request.message_sender,
        message_subject=request.message_subject,
        user_intent=request.user_intent,
        preferred_tone=request.preferred_tone or profile_tone,
        current_energy=request.current_energy,
        context_note=request.context_note,
        include_boundary=request.include_boundary_option,
        max_length=request.max_length,
    )


# ── Fallback rule-based drafts ─────────────────────────────────────────

def _build_fallback_options(
    intent: Optional[str],
    include_boundary: bool,
    is_low_energy: bool,
) -> List[ReplyDraftOption]:
    """
    Rule-based drafts — used when LLM fails, rate-limited, or unavailable.
    Intent keywords: accept | decline | delay
    """
    intent_lower = (intent or "").lower()

    if "accept" in intent_lower:
        short = "Yes, that works for me. Thanks."
        warm = "Yes, that works for me. Thanks for checking."
        detailed = (
            "Yes, that works for me. I'm happy to go ahead with this "
            "and will follow up if anything changes."
        )
    elif "decline" in intent_lower:
        short = "Thanks for thinking of me, but I can't take this on right now."
        warm = "Thanks for reaching out. I appreciate it, but I'm not able to take this on right now."
        detailed = (
            "Thanks for reaching out and thinking of me. "
            "I'm not able to take this on right now, but I appreciate you asking."
        )
    elif "delay" in intent_lower or "more time" in intent_lower:
        short = "Thanks for your message. I'll get back to you tomorrow."
        warm = (
            "Thanks for your message. I need a little more time to respond properly, "
            "and I'll get back to you tomorrow."
        )
        detailed = (
            "Thanks for your message. I've received this and want to respond properly. "
            "I need a little more time, so I'll get back to you tomorrow."
        )
    else:
        short = "Thanks for your message. I'll take a look and get back to you soon."
        warm = "Thanks for reaching out. I'll review this and send you a proper response soon."
        detailed = (
            "Thanks for your message. I've received it and will review the details carefully. "
            "I'll follow up with a clearer answer once I've had time to check everything."
        )

    # If low energy, trim the detailed option
    if is_low_energy:
        detailed = warm

    options = [
        ReplyDraftOption(type="short", text=short),
        ReplyDraftOption(type="warm", text=warm),
        ReplyDraftOption(type="detailed", text=detailed),
    ]

    if include_boundary:
        options.append(
            ReplyDraftOption(
                type="boundary",
                text=(
                    "Thanks for your message. I'm not able to take this on today, "
                    "but I can follow up when I have more capacity."
                ),
            )
        )

    return options


def _should_include_boundary(request: ReplyDraftRequest) -> bool:
    """Determine whether a boundary reply should be included."""
    if not request.include_boundary_option:
        return False
    if request.current_energy is not None and request.current_energy < 40:
        return True
    intent_lower = (request.user_intent or "").lower()
    return any(kw in intent_lower for kw in ("decline", "delay", "boundary", "not available"))


# ── Main service function ──────────────────────────────────────────────

async def draft_reply(
    db: Session,
    user_id: str,
    request: ReplyDraftRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> ReplyDraftSchema:
    """
    Main entry point for reply drafting (hardened Day 9).

    1. Fetch user profile for preferred tone.
    2. Safety scan for prompt injection.
    3. Rate limit check.
    4. Build LLM prompt (versioned).
    5. Call LLM (mock by default).
    6. Validate output; fallback on failure.
    7. Enforce boundary logic.
    8. Log usage metadata (no prompt text, no message text).
    9. Persist draft to DB.
    10. Return ReplyDraft schema.

    This function NEVER sends messages.
    """
    # ── 1. Profile tone ────────────────────────────────────────────────
    profile = user_profile_repository.get_or_create_default(db, user_id)
    profile_tone = getattr(profile, "preferred_tone", None)

    # ── 2. Determine settings ──────────────────────────────────────────
    is_low_energy = request.current_energy is not None and request.current_energy < 30
    include_boundary = _should_include_boundary(request)

    # ── 3. Prompt injection safety scan ───────────────────────────────
    safety = detect_prompt_injection_risk(request.original_message)
    injection_detected = safety["risk_detected"]

    # ── 4. LLM client setup ────────────────────────────────────────────
    if llm_client is None:
        llm_client = get_llm_client()

    client_class = llm_client.__class__.__name__
    provider = "mock" if client_class == "MockLLMClient" else client_class.lower().replace("client", "")
    from app.core.llm_config import get_llm_settings
    settings = get_llm_settings()
    model = settings.llm_model or None

    # ── 5. Rate limit check ────────────────────────────────────────────
    rate_result = check_rate_limit(db, user_id)
    source = "mock"
    options: List[ReplyDraftOption] = []
    llm_status = "success"
    error_type = None
    latency_ms = None

    if not rate_result["allowed"]:
        logger.warning("Rate limit exceeded for user %s: %s", user_id, rate_result["reason"])
        log_rate_limit_skip(
            db=db, user_id=user_id, feature="reply_drafting",
            provider=provider, reason=rate_result["reason"],
            prompt_version=PROMPT_VERSION,
        )
        options = _build_fallback_options(
            intent=request.user_intent,
            include_boundary=include_boundary,
            is_low_energy=is_low_energy,
        )
        source = "fallback"
        llm_status = "skipped_rate_limit"
    else:
        # ── 6. Build prompt ────────────────────────────────────────────
        user_prompt = _build_user_prompt(request, profile_tone)

        # If injection risk detected, prepend safety note
        if injection_detected:
            user_prompt = build_safety_prefix(safety["risk_terms"]) + user_prompt

        # ── 7. LLM call ────────────────────────────────────────────────
        t0 = time.monotonic()
        try:
            raw = await llm_client.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema_name="reply_draft",
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            validated = ReplyDraftLLMOutput.model_validate(raw)
            options = validated.draft_options
            source = "mock" if client_class == "MockLLMClient" else "llm"
            llm_status = "success"

            # Boundary enforcement
            boundary_in_options = any(o.type == "boundary" for o in options)
            if include_boundary and not boundary_in_options:
                options.append(
                    ReplyDraftOption(
                        type="boundary",
                        text=(
                            "Thanks for your message. I'm not able to take this on today, "
                            "but I can follow up when I have more capacity."
                        ),
                    )
                )
            elif not include_boundary:
                options = [o for o in options if o.type != "boundary"]

        except (LLMError, ValueError) as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("LLM call failed for reply draft — using fallback. Reason: %s", exc)
            options = _build_fallback_options(
                intent=request.user_intent,
                include_boundary=include_boundary,
                is_low_energy=is_low_energy,
            )
            source = "fallback"
            llm_status = "fallback"
            error_type = type(exc).__name__

        # ── 8. Log usage metadata (no prompt/message text) ────────────
        cost = estimate_llm_cost(provider, model, None, None)  # tokens null for mock
        request_meta = {
            "schema_name": "reply_draft",
            "prompt_version": PROMPT_VERSION,
            "include_boundary": include_boundary,
            "is_low_energy": is_low_energy,
        }
        if injection_detected:
            request_meta["prompt_injection_risk"] = True
            request_meta["risk_terms"] = safety["risk_terms"]

        llm_usage_repository.create_log(
            db=db,
            user_id=user_id,
            feature="reply_drafting",
            provider=provider,
            model=model,
            prompt_version=PROMPT_VERSION,
            status=llm_status,
            error_type=error_type,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            request_metadata=request_meta,
        )

    # ── 9. Persist draft ────────────────────────────────────────────────
    from app.repositories.privacy_preferences_repository import privacy_preferences_repository
    prefs = privacy_preferences_repository.get_or_create_default(db, user_id)
    stored_original = request.original_message
    if not prefs.store_reply_original_messages:
        stored_original = "[redacted]"

    row = reply_draft_repository.create(
        db=db,
        user_id=user_id,
        source_type=request.message_channel if request.message_channel != "manual" else "manual",
        original_message=stored_original,
        message_sender=request.message_sender,
        message_subject=request.message_subject,
        message_channel=request.message_channel,
        user_intent=request.user_intent,
        preferred_tone=request.preferred_tone or profile_tone,
        context_note=request.context_note,
        draft_options=[o.model_dump() for o in options],
        source=source,
    )

    # ── 10. Return ──────────────────────────────────────────────────────
    return ReplyDraftSchema.model_validate(row)

