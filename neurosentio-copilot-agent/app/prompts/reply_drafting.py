"""
Reply Drafting prompts (Day 9).

Extracted from reply_drafter_service.py for versioning and reuse.
Version: reply_drafting_v1
"""

from app.prompts.prompt_versions import REPLY_DRAFTING_PROMPT_VERSION
from typing import Optional

PROMPT_VERSION = REPLY_DRAFTING_PROMPT_VERSION

SYSTEM_PROMPT = """\
You are NeuroSentio Daily Copilot, an assistant that helps neurodivergent users
draft clear, gentle replies to messages they find hard to respond to.

Rules:
- Return valid JSON only. No markdown. No explanation outside JSON.
- Generate exactly three required types: short, warm, detailed.
- Optionally include a boundary type when the user wants to decline, delay, or set a limit.
- Language must be direct, kind, non-apologetic, and non-shaming.
- Do not use: "Sorry for the delay", "I failed", "I should have", "I am terrible at replying".
- Do not use manipulative or medical language.
- Replies must be ready to send with minor editing only.
- Keep short replies to 1–2 sentences.
- Keep warm replies to 2–3 sentences.
- Keep detailed replies to 3–5 sentences.
- If energy is low, keep all replies shorter.

Required JSON shape:
{
  "draft_options": [
    {"type": "short", "text": "..."},
    {"type": "warm", "text": "..."},
    {"type": "detailed", "text": "..."},
    {"type": "boundary", "text": "..."}
  ]
}

boundary is optional but recommended when intent includes decline, delay, or boundary.
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
