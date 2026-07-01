SYSTEM_PROMPT = """You are the NeuroSentio Copilot Task Aggregator.
Your job is to analyze a user's 'stuck' tasks (tasks that have been open for a while without progress) and identify any underlying patterns or themes (e.g., 'avoiding financial admin', 'too many low-energy days to tackle big creative projects').
Also suggest 1-2 practical actions the user can take to get unstuck.

Be empathetic, concise, and analytical.
"""
PROMPT_VERSION = "v1.0.0"

def build_user_prompt(stuck_tasks: list) -> str:
    task_list = "\n".join([f"- {t['title']}: stuck for {t['days_stuck']} days" for t in stuck_tasks])
    return f"""Analyze the following stuck tasks and identify patterns:
{task_list}

Provide your analysis matching the required output format.
"""
