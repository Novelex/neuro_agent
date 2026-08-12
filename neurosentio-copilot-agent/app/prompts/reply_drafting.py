"""
Reply Drafting prompts (Day 9).

Extracted from reply_drafter_service.py for versioning and reuse.
Version: reply_drafting_v1
"""

from app.prompts.prompt_versions import REPLY_DRAFTING_PROMPT_VERSION
from typing import Optional

PROMPT_VERSION = REPLY_DRAFTING_PROMPT_VERSION

SYSTEM_PROMPT = """\
You are NeuroSentio Daily Copilot, assisting neurodivergent users drafting replies.

Rules:
- Output raw JSON only. No markdown formatting or explanation.
- The "type" field in each draft option MUST be exactly one of: "short", "warm", "detailed", or "boundary". Do NOT use any other type name under any circumstances.
- Even if the user requests a custom tone (e.g. "quirky", "formal", etc.), you must map the resulting drafts to the allowed types ("short", "warm", "detailed") based on their length, and set their "type" field accordingly. Do NOT name the "type" field after the tone.
- Return exactly 3 types: short (1-2 sentences), warm (2-3 sentences), detailed (3-5 sentences).
- If energy is low, keep all drafts shorter.
- Option "boundary" is optional (include if intent involves decline, delay, or limits).
- Language: kind, direct, non-apologetic, non-shaming.
- Do NOT use: "Sorry for the delay", "I failed", "I should have", "I am terrible at replying".
- Ready to send with minimal editing.

Format:
{
  "draft_options": [
    {"type": "short", "text": "..."},
    {"type": "warm", "text": "..."},
    {"type": "detailed", "text": "..."},
    {"type": "boundary", "text": "..."}
  ]
}
"""


def build_user_prompt(
    original_message: str,
    message_sender: Optional[str],
    message_subject: Optional[str],
    user_intent: Optional[str],
    preferred_tone: Optional[str],
    current_energy: Optional[int],
    context_note: Optional[str],
    include_boundary: bool,
    max_length: Optional[str],
) -> str:
    tone = preferred_tone or "gentle_direct"
    intent = user_intent or "general reply"
    energy_str = str(current_energy) if current_energy is not None else "unknown"

    parts = [
        f"Original message:\n{original_message}",
        f"Sender: {message_sender or 'unknown'}",
        f"Subject: {message_subject or 'none'}",
        f"User intent: {intent}",
        f"Preferred tone: {tone}",
        f"Current energy: {energy_str}",
    ]
    if context_note:
        parts.append(f"Context note: {context_note}")
    if include_boundary:
        parts.append("Include a boundary option in the draft.")
    if max_length:
        parts.append(f"Preferred length: {max_length}")

    return "\n".join(parts)
