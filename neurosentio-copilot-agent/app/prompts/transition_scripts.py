"""
Transition Script prompts (Day 9).

Version: transition_script_v1
Currently transition scripts are rule-based, not LLM-driven.
This module is a placeholder for when LLM integration is added (Day 11+).
"""

from app.prompts.prompt_versions import TRANSITION_SCRIPT_PROMPT_VERSION

PROMPT_VERSION = TRANSITION_SCRIPT_PROMPT_VERSION

SYSTEM_PROMPT = """\
You are NeuroSentio Daily Copilot. Generate a gentle, step-by-step transition script
to help a neurodivergent user navigate the transition described.

Rules:
- Return valid JSON only.
- Each step must be one clear, concrete action.
- Keep steps short — under 160 characters each.
- Use gentle, non-shaming language.
- If energy is low, return 3 steps maximum.

Required JSON:
{
  "script_steps": ["step 1", "step 2", ...]
}
"""

from typing import Optional

def build_user_prompt(
    transition_type: str,
    next_task_title: Optional[str] = None,
    current_energy: Optional[int] = None,
    context_note: Optional[str] = None,
    sensory_state: Optional[str] = None,
    max_steps: int = 5
) -> str:
    parts = []
    
    if next_task_title and transition_type == "custom":
        parts.append(f"Transition Type: Custom")
        parts.append(f"Target Activity / Next Task: {next_task_title}")
    else:
        parts.append(f"Transition Type: {transition_type.replace('_', ' ').title()}")
        if next_task_title:
            parts.append(f"Next Task: {next_task_title}")
            
    if current_energy is not None:
        parts.append(f"User Energy Level: {current_energy}/100")
        if current_energy < 30:
            parts.append("Note: Energy is very low. Provide an extremely gentle recovery-focused script with minimal demands.")
            
    if sensory_state:
        parts.append(f"Current Sensory State: {sensory_state}")
        
    if context_note:
        parts.append(f"Additional Context: {context_note}")
        
    parts.append(f"Maximum Steps Required: {max_steps}")
    
    return "\n".join(parts)
