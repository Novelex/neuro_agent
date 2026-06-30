"""
Raw SQL queries for the Supabase AI Proxy.
All queries use SQLAlchemy Core (text()) to communicate with the shared Supabase schema.
"""

from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session
import json

# ─── Reads (from Flutter's schema) ────────────────────────────────────

def get_open_tasks(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """Fetch incomplete tasks from planner_tasks."""
    query = text('''
        SELECT id, title, subtitle, time, date, isCompleted 
        FROM public.planner_tasks 
        WHERE user_id = :uid AND "isCompleted" = false
        ORDER BY created_at DESC
    ''')
    result = db.execute(query, {"uid": user_id})
    return [dict(row._mapping) for row in result]

def get_task(db: Session, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single task by ID."""
    query = text('''
        SELECT id, title, subtitle, time, date, isCompleted 
        FROM public.planner_tasks 
        WHERE user_id = :uid AND id = :tid
    ''')
    result = db.execute(query, {"uid": user_id, "tid": task_id}).fetchone()
    if result:
        return dict(result._mapping)
    return None

def get_latest_energy_level(db: Session, user_id: str) -> Optional[int]:
    """Fetch the most recent energy log level (0-10) and convert to 0-100 scale."""
    query = text('''
        SELECT level 
        FROM public.energy_logs 
        WHERE user_id = :uid 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    result = db.execute(query, {"uid": user_id}).fetchone()
    if result:
        # User's DB scale is 0-10, backend AI expects 0-100
        return result[0] * 10
    return None


def get_user_settings(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user settings (tags, panic message)."""
    query = text('''
        SELECT panic_message, selected_tags, energy_reminders, theme 
        FROM public.settings 
        WHERE user_id = :uid
    ''')
    result = db.execute(query, {"uid": user_id}).fetchone()
    if result:
        return dict(result._mapping)
    return None


# ─── Writes (to new AI tables) ────────────────────────────────────────

def log_llm_usage(
    db: Session, 
    user_id: str, 
    feature: str, 
    provider: str, 
    model: str, 
    status: str, 
    latency_ms: Optional[int] = None, 
    cost: Optional[float] = None
):
    """Log an LLM usage event for rate limiting and billing tracking."""
    query = text('''
        INSERT INTO public.llm_usage_logs 
        (user_id, feature, provider, model, status, latency_ms, estimated_cost_usd) 
        VALUES (:uid, :feat, :prov, :mod, :stat, :lat, :cost)
    ''')
    db.execute(query, {
        "uid": user_id, "feat": feature, "prov": provider, 
        "mod": model, "stat": status, "lat": latency_ms, "cost": cost
    })
    db.commit()


def count_user_logs_today(db: Session, user_id: str) -> int:
    query = text('''
        SELECT COUNT(*) 
        FROM public.llm_usage_logs 
        WHERE user_id = :uid AND DATE(created_at) = CURRENT_DATE
    ''')
    result = db.execute(query, {"uid": user_id}).fetchone()
    return result[0] if result else 0


def count_user_logs_this_month(db: Session, user_id: str) -> int:
    query = text('''
        SELECT COUNT(*) 
        FROM public.llm_usage_logs 
        WHERE user_id = :uid 
        AND EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
        AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
    ''')
    result = db.execute(query, {"uid": user_id}).fetchone()
    return result[0] if result else 0


def save_micro_actions(db: Session, user_id: str, task_id: Optional[str], plan_id: Optional[str], actions: List[Dict[str, Any]]) -> None:
    """Save decomposed micro-actions."""
    query = text('''
        INSERT INTO public.ai_micro_actions 
        (user_id, task_id, plan_id, parent_id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, sort_order) 
        VALUES (:uid, :tid, :pid, :par, :title, :desc, :dur, :ec, :sc, :fl, :so)
    ''')
    for action in actions:
        db.execute(query, {
            "uid": user_id,
            "tid": task_id,
            "pid": plan_id,
            "par": action.get("parent_id"),
            "title": action["title"],
            "desc": action.get("description"),
            "dur": action.get("duration_minutes", 5),
            "ec": action.get("energy_cost", "low"),
            "sc": action.get("sensory_cost", "low"),
            "fl": action.get("friction_level", "low"),
            "so": action.get("sort_order", 0)
        })
    db.commit()


def save_morning_plan(db: Session, user_id: str, plan_date: date, mode: str, summary: str, message: str, total_minutes: int, risk_score: int) -> str:
    """Save a morning plan and return its ID."""
    query = text('''
        INSERT INTO public.ai_morning_plans 
        (user_id, plan_date, mode, summary, message, total_scheduled_minutes, overload_risk_score) 
        VALUES (:uid, :pdate, :mode, :sum, :msg, :mins, :risk)
        ON CONFLICT (user_id, plan_date) 
        DO UPDATE SET mode = EXCLUDED.mode, summary = EXCLUDED.summary, 
                      message = EXCLUDED.message, total_scheduled_minutes = EXCLUDED.total_scheduled_minutes, 
                      overload_risk_score = EXCLUDED.overload_risk_score
        RETURNING id
    ''')
    result = db.execute(query, {
        "uid": user_id, "pdate": plan_date, "mode": mode,
        "sum": summary, "msg": message, "mins": total_minutes, "risk": risk_score
    })
    plan_id = result.fetchone()[0]
    db.commit()
    return str(plan_id)


def get_today_morning_plan(db: Session, user_id: str, plan_date: date) -> Optional[Dict[str, Any]]:
    query = text('''
        SELECT id, mode, summary, message, total_scheduled_minutes, overload_risk_score
        FROM public.ai_morning_plans
        WHERE user_id = :uid AND plan_date = :pdate
    ''')
    result = db.execute(query, {"uid": user_id, "pdate": plan_date}).fetchone()
    if result:
        return dict(result._mapping)
    return None


def get_plan_micro_actions(db: Session, plan_id: str) -> List[Dict[str, Any]]:
    query = text('''
        SELECT id, title, description, duration_minutes, energy_cost, status, sort_order, task_id
        FROM public.ai_micro_actions
        WHERE plan_id = :pid
        ORDER BY sort_order ASC
    ''')
    result = db.execute(query, {"pid": plan_id})
    return [dict(row._mapping) for row in result]


def save_reply_draft(db: Session, user_id: str, original_message: str, user_intent: str, options: List[Dict[str, Any]], source: str = "llm") -> None:
    query = text('''
        INSERT INTO public.ai_reply_drafts 
        (user_id, original_message, user_intent, draft_options, source) 
        VALUES (:uid, :msg, :int, :opt, :src)
    ''')
    db.execute(query, {
        "uid": user_id, "msg": original_message, "int": user_intent or "", 
        "opt": json.dumps(options), "src": source
    })
    db.commit()


def save_transition_script(db: Session, user_id: str, transition_type: str, title: str, steps: List[str], source: str = "llm") -> None:
    query = text('''
        INSERT INTO public.ai_transition_scripts 
        (user_id, transition_type, title, script_steps, source) 
        VALUES (:uid, :ttype, :title, :steps, :src)
    ''')
    db.execute(query, {
        "uid": user_id, "ttype": transition_type, "title": title, 
        "steps": json.dumps(steps), "src": source
    })
    db.commit()


def get_micro_actions_for_task(db: Session, user_id: str, task_id: str) -> List[Dict[str, Any]]:
    query = text('''
        SELECT id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, status, sort_order, task_id, parent_id
        FROM public.ai_micro_actions
        WHERE user_id = :uid AND task_id = :tid
        ORDER BY sort_order ASC
    ''')
    result = db.execute(query, {"uid": user_id, "tid": task_id})
    return [dict(row._mapping) for row in result]


def delete_open_micro_actions_for_task(db: Session, user_id: str, task_id: str) -> None:
    query = text('''
        DELETE FROM public.ai_micro_actions
        WHERE user_id = :uid AND task_id = :tid AND status = 'open'
    ''')
    db.execute(query, {"uid": user_id, "tid": task_id})
    db.commit()


def get_micro_action_by_id(db: Session, user_id: str, micro_action_id: str) -> Optional[Dict[str, Any]]:
    query = text('''
        SELECT id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, status, sort_order, task_id, parent_id
        FROM public.ai_micro_actions
        WHERE user_id = :uid AND id = :maid
    ''')
    result = db.execute(query, {"uid": user_id, "maid": micro_action_id}).fetchone()
    if result:
        return dict(result._mapping)
    return None

def set_micro_action_status(db: Session, user_id: str, micro_action_id: str, status: str) -> None:
    query = text('''
        UPDATE public.ai_micro_actions
        SET status = :status
        WHERE user_id = :uid AND id = :maid
    ''')
    db.execute(query, {"uid": user_id, "maid": micro_action_id, "status": status})
    db.commit()

def get_max_sort_order(db: Session, user_id: str, task_id: str) -> int:
    query = text('''
        SELECT MAX(sort_order)
        FROM public.ai_micro_actions
        WHERE user_id = :uid AND task_id = :tid
    ''')
    result = db.execute(query, {"uid": user_id, "tid": task_id}).fetchone()
    if result and result[0] is not None:
        return result[0]
    return 0
