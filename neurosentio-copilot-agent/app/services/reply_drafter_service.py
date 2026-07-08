"""
Reply Drafter Service.

Generates draft replies using the LLM client.
Refactored to use raw Supabase SQL queries.
"""

import logging
import time
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.llm.base import BaseLLMClient, LLMError
from app.llm.client_factory import get_llm_client
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


def _build_fallback_options(
    intent: Optional[str],
    include_boundary: bool,
    is_low_energy: bool,
) -> List[ReplyDraftOption]:
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
        warm = "I appreciate you reaching out, but I don't have the capacity for this right now."
        detailed = (
            "Thank you for thinking of me. Unfortunately, my plate is currently full "
            "so I won't be able to take this on. I'll let you know if that changes."
        )
    else:
        short = "Got it, thanks."
        warm = "Thanks for the message. I'll get back to you soon."
        detailed = (
            "Thanks for your message. I've received it and will review the details carefully. "
            "I'll follow up with a clearer answer once I've had time to check everything."
        )

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
    if not request.include_boundary_option:
        return False
    if request.current_energy is not None and request.current_energy < 40:
        return True
    intent_lower = (request.user_intent or "").lower()
    return any(kw in intent_lower for kw in ("decline", "delay", "boundary", "not available"))


async def draft_reply(
    db: Connection,
    user_id: str,
    request: ReplyDraftRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> ReplyDraftSchema:
    
    settings = sq.get_user_settings(db, user_id)
    profile_tone = "professional" # default fallback
    
    is_low_energy = request.current_energy is not None and request.current_energy < 30
    include_boundary = _should_include_boundary(request)

    safety = detect_prompt_injection_risk(request.original_message)
    injection_detected = safety["risk_detected"]

    source = "llm"
    options: List[ReplyDraftOption] = []
    llm_status = "success"
    error_type = None
    latency_ms = None
    provider = "unknown"
    model = ""

    from app.core.llm_config import get_llm_settings
    llm_settings = get_llm_settings()
    model = llm_settings.llm_model or ""

    t0 = time.monotonic()
    try:
        if llm_client is None:
            llm_client = get_llm_client()

        client_class = llm_client.__class__.__name__
        provider = client_class.lower().replace("client", "")

        rate_result = check_rate_limit(db, user_id)
        if not rate_result["allowed"]:
            logger.warning("Rate limit exceeded for user %s: %s", user_id, rate_result["reason"])
            sq.log_llm_usage(
                conn=db, user_id=user_id, feature="reply_drafting",
                provider=provider, model=model or "", status="rate_limited",
            )
            options = _build_fallback_options(
                intent=request.user_intent,
                include_boundary=include_boundary,
                is_low_energy=is_low_energy,
            )
            source = "fallback"
            llm_status = "skipped_rate_limit"
        else:
            user_prompt = _build_user_prompt(request, profile_tone)
            if injection_detected:
                user_prompt = build_safety_prefix(safety["risk_terms"]) + user_prompt

            raw = await llm_client.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema_name="reply_draft",
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            validated = ReplyDraftLLMOutput.model_validate(raw)
            options = validated.draft_options
            source = "llm"
            llm_status = "success"

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
        logger.warning("LLM setup or call failed for reply draft — using fallback. Reason: %s", exc)
        options = _build_fallback_options(
            intent=request.user_intent,
            include_boundary=include_boundary,
            is_low_energy=is_low_energy,
        )
        source = "fallback"
        llm_status = "fallback"
        error_type = type(exc).__name__

    cost = estimate_llm_cost(provider, model, None, None) 
    sq.log_llm_usage(
        conn=db, user_id=user_id, feature="reply_drafting",
        provider=provider, model=model or "", status=llm_status,
        latency_ms=latency_ms, cost=cost
    )

    # ── 9. Persist draft ────────────────────────────────────────────────
    stored_original = request.original_message

    sq.save_reply_draft(
        conn=db,
        user_id=user_id,
        original_message=stored_original,
        user_intent=request.user_intent or "",
        options=[o.model_dump() for o in options],
        source=source
    )
    
    draft_id = str(uuid.uuid4())

    return ReplyDraftSchema(
        id=draft_id,
        user_id=user_id,
        original_message=stored_original,
        message_sender=request.message_sender,
        message_subject=request.message_subject,
        message_channel=request.message_channel or "manual",
        user_intent=request.user_intent,
        preferred_tone=request.preferred_tone or profile_tone,
        context_note=request.context_note,
        draft_options=options,
        source=source,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
