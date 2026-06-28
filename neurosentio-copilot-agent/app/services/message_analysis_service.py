"""
Message Analysis Service.

Analyzes message metadata (subject + snippet only) to:
- detect keyword groups
- detect user intent
- calculate urgency score
- determine if reply is needed
- build a message summary

Privacy: Never processes or stores full message bodies.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

# ─────────────────────────────────────────────────────────────────────
# Keyword groups (subject + snippet only)
# ─────────────────────────────────────────────────────────────────────

KEYWORD_GROUPS: Dict[str, List[str]] = {
    "urgent": ["urgent", "asap", "immediately", "right away", "critical", "emergency"],
    "deadline": ["deadline", "due", "by tonight", "by tomorrow", "before eod", "end of day", "eod"],
    "question": ["?", "can you", "could you", "would you", "are you able"],
    "request": ["please send", "need", "requested", "can you share", "provide", "send me"],
    "scheduling": ["meeting", "call", "schedule", "reschedule", "availability", "sync", "calendar"],
    "follow_up": ["following up", "checking in", "reminder", "just wanted to", "circling back"],
}


def detect_keywords(text: str) -> List[str]:
    """
    Detect keyword groups present in text (subject + snippet).
    Returns list of matching group names.
    """
    text_lower = text.lower()
    text_processed = text_lower.replace("no need", "")
    found = []
    for group, keywords in KEYWORD_GROUPS.items():
        if any(kw in text_processed for kw in keywords):
            found.append(group)
    return found


def detect_intent(subject: Optional[str], snippet: Optional[str]) -> str:
    """
    Determine the primary intent of a message.

    Priority order:
    urgent > deadline > question > request > scheduling > follow_up > FYI > unknown
    """
    text = " ".join(filter(None, [subject, snippet]))
    if not text.strip():
        return "unknown"

    keywords = detect_keywords(text)

    priority_order = ["urgent", "deadline", "question", "request", "scheduling", "follow_up"]
    for intent in priority_order:
        if intent in keywords:
            return intent

    # FYI if the text doesn't ask for anything
    if text:
        return "FYI"
    return "unknown"


def calculate_urgency_score(
    detected_intent: str,
    detected_keywords: List[str],
    is_read: bool,
    received_at: Optional[datetime],
) -> int:
    """
    Calculate urgency score 0-100.

    Rules:
    - urgent keyword: +40
    - deadline keyword: +30
    - question/request: +20
    - unread: +10
    - received within last 24 hours: +10
    - received more than 7 days ago and still unread: +20
    """
    score = 0

    if "urgent" in detected_keywords:
        score += 40
    if "deadline" in detected_keywords:
        score += 30
    if detected_intent in ("question", "request"):
        score += 20
    if not is_read:
        score += 10

    if received_at is not None:
        now = datetime.now(timezone.utc)
        # Normalize to UTC-aware
        if received_at.tzinfo is None:
            received_at_utc = received_at.replace(tzinfo=timezone.utc)
        else:
            received_at_utc = received_at

        age = now - received_at_utc
        if age < timedelta(hours=24):
            score += 10
        elif age > timedelta(days=7) and not is_read:
            score += 20

    return min(score, 100)


def determine_needs_reply(detected_intent: str, urgency_score: int) -> bool:
    """
    True if:
    - detected_intent is question, request, deadline, scheduling, follow_up, urgent
    - OR urgency_score >= 40
    """
    reply_intents = {"question", "request", "deadline", "scheduling", "follow_up", "urgent"}
    return detected_intent in reply_intents or urgency_score >= 40


def sanitize_metadata(raw_metadata: Optional[dict]) -> Optional[dict]:
    """
    Strip privacy-sensitive fields from metadata.
    Removes: body, full_body, html, text, raw, attachments,
             auth_tokens, access_token, refresh_token
    """
    if not raw_metadata:
        return None

    STRIP_KEYS = {
        "body", "full_body", "html", "text", "raw", "attachments",
        "auth_tokens", "access_token", "refresh_token"
    }

    return {k: v for k, v in raw_metadata.items() if k not in STRIP_KEYS}


def analyze_message(
    source: str,
    external_message_id: Optional[str],
    channel: str,
    sender: Optional[str],
    subject: Optional[str],
    snippet: Optional[str],
    received_at: Optional[datetime],
    is_read: bool,
    metadata: Optional[dict],
) -> Dict[str, Any]:
    """
    Analyze a single message and return a dict ready for DB insertion.
    """
    from datetime import datetime as dt
    if received_at is None:
        received_at = datetime.now(timezone.utc)

    text = " ".join(filter(None, [subject, snippet]))
    detected_keywords = detect_keywords(text)
    detected_intent = detect_intent(subject, snippet)

    urgency_score = calculate_urgency_score(
        detected_intent, detected_keywords, is_read, received_at
    )
    needs_reply = determine_needs_reply(detected_intent, urgency_score)
    sanitized_meta = sanitize_metadata(metadata)

    return {
        "source": source,
        "external_message_id": external_message_id,
        "channel": channel,
        "sender": sender,
        "subject": subject,
        "snippet": snippet,
        "received_at": received_at,
        "is_read": is_read,
        "needs_reply": needs_reply,
        "urgency_score": urgency_score,
        "detected_intent": detected_intent,
        "detected_keywords": detected_keywords,
        "metadata": sanitized_meta,
    }


def build_message_summary(messages) -> Dict[str, Any]:
    """
    Build a MessageSummary from a list of MessageItem DB objects.
    """
    total_count = len(messages)
    unread_count = sum(1 for m in messages if not m.is_read)
    needs_reply_count = sum(1 for m in messages if m.needs_reply)
    urgent_count = sum(1 for m in messages if m.urgency_score >= 40)

    # Top urgent messages (sorted by urgency desc)
    urgent_msgs = sorted(
        [m for m in messages if m.urgency_score >= 40],
        key=lambda m: m.urgency_score,
        reverse=True
    )[:5]

    top_urgent_messages = [
        {
            "id": m.id,
            "sender": m.sender,
            "subject": m.subject,
            "urgency_score": m.urgency_score,
            "detected_intent": m.detected_intent,
        }
        for m in urgent_msgs
    ]

    # Build recommendation
    if urgent_count >= 3:
        recommendation = (
            "There are several high-urgency messages. "
            "Consider drafting one short reply first."
        )
    elif urgent_count >= 1 or needs_reply_count >= 1:
        recommendation = (
            "You have a few messages that may need a reply. "
            "Start with the highest urgency one."
        )
    else:
        recommendation = (
            "No urgent messages found. You can leave replies for later."
        )

    return {
        "total_count": total_count,
        "unread_count": unread_count,
        "needs_reply_count": needs_reply_count,
        "urgent_count": urgent_count,
        "top_urgent_messages": top_urgent_messages,
        "recommendation": recommendation,
    }
