"""Prompt versions registry (Day 9)."""

TASK_DECOMPOSITION_PROMPT_VERSION = "task_decomposition_v1"
REPLY_DRAFTING_PROMPT_VERSION = "reply_drafting_v1"
TRANSITION_SCRIPT_PROMPT_VERSION = "transition_script_v1"
MORNING_PLAN_PROMPT_VERSION = "morning_plan_v1"

# All registered versions — used for validation in tests
ALL_PROMPT_VERSIONS = {
    "task_decomposition": TASK_DECOMPOSITION_PROMPT_VERSION,
    "reply_drafting": REPLY_DRAFTING_PROMPT_VERSION,
    "transition_script": TRANSITION_SCRIPT_PROMPT_VERSION,
    "morning_plan": MORNING_PLAN_PROMPT_VERSION,
}
