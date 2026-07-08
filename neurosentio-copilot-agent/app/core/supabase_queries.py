"""
Raw SQL queries for the Supabase AI Proxy.
Uses pure psycopg2 to communicate with the shared Supabase schema.
"""

from typing import List, Dict, Any, Optional
from datetime import date
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Type hint for a psycopg2 connection
Connection = psycopg2.extensions.connection

# ─── Reads (from Flutter's schema) ────────────────────────────────────

def get_open_tasks(conn: Connection, user_id: str) -> List[Dict[str, Any]]:
    """Fetch incomplete tasks from planner_tasks."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, title, subtitle, time, date, created_at, "isCompleted" 
            FROM public.planner_tasks 
            WHERE user_id = %(uid)s AND "isCompleted" = false
            ORDER BY created_at DESC
        ''', {"uid": user_id})
        return [dict(row) for row in cur.fetchall()]

def get_task(conn: Connection, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single task by ID."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, title, subtitle, time, date, "isCompleted" 
            FROM public.planner_tasks 
            WHERE user_id = %(uid)s AND id = %(tid)s
        ''', {"uid": user_id, "tid": task_id})
        result = cur.fetchone()
        return dict(result) if result else None

def get_latest_energy_level(conn: Connection, user_id: str) -> Optional[int]:
    """Fetch the most recent energy log level (0-10) and convert to 0-100 scale."""
    with conn.cursor() as cur:
        cur.execute('''
            SELECT level 
            FROM public.energy_logs 
            WHERE user_id = %(uid)s 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', {"uid": user_id})
        result = cur.fetchone()
        return result[0] * 10 if result else None

def get_energy_logs_for_last_7_days(conn: Connection, user_id: str) -> List[Dict[str, Any]]:
    """Fetch all energy logs for the last 7 days."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, level, timestamp
            FROM public.energy_logs
            WHERE user_id = %(uid)s 
            AND timestamp >= NOW() - INTERVAL '7 days'
            ORDER BY timestamp ASC
        ''', {"uid": user_id})
        return [dict(row) for row in cur.fetchall()]

def get_user_settings(conn: Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user settings (tags, panic message)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT panic_message, selected_tags, energy_reminders, theme 
            FROM public.settings 
            WHERE user_id = %(uid)s
        ''', {"uid": user_id})
        result = cur.fetchone()
        return dict(result) if result else None

# ─── Writes (to new AI tables) ────────────────────────────────────────

def log_llm_usage(
    conn: Connection, 
    user_id: str, 
    feature: str, 
    provider: str, 
    model: str, 
    status: str, 
    latency_ms: Optional[int] = None, 
    cost: Optional[float] = None
):
    """Log an LLM usage event for rate limiting and billing tracking."""
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO public.llm_usage_logs 
            (user_id, feature, provider, model, status, latency_ms, estimated_cost_usd) 
            VALUES (%(uid)s, %(feat)s, %(prov)s, %(mod)s, %(stat)s, %(lat)s, %(cost)s)
        ''', {
            "uid": user_id, "feat": feature, "prov": provider, 
            "mod": model, "stat": status, "lat": latency_ms, "cost": cost
        })
    conn.commit()

def count_user_logs_today(conn: Connection, user_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*) 
            FROM public.llm_usage_logs 
            WHERE user_id = %(uid)s AND DATE(created_at) = CURRENT_DATE
        ''', {"uid": user_id})
        result = cur.fetchone()
        return result[0] if result else 0

def count_user_logs_this_month(conn: Connection, user_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*) 
            FROM public.llm_usage_logs 
            WHERE user_id = %(uid)s 
            AND EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
        ''', {"uid": user_id})
        result = cur.fetchone()
        return result[0] if result else 0

def save_micro_actions(conn: Connection, user_id: str, task_id: Optional[str], plan_id: Optional[str], actions: List[Dict[str, Any]]) -> None:
    """Save decomposed micro-actions."""
    with conn.cursor() as cur:
        for action in actions:
            cur.execute('''
                INSERT INTO public.ai_micro_actions 
                (user_id, task_id, plan_id, parent_id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, sort_order) 
                VALUES (%(uid)s, %(tid)s, %(pid)s, %(par)s, %(title)s, %(desc)s, %(dur)s, %(ec)s, %(sc)s, %(fl)s, %(so)s)
            ''', {
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
    conn.commit()

def save_morning_plan(conn: Connection, user_id: str, plan_date: date, mode: str, summary: str, message: str, total_minutes: int, risk_score: int) -> str:
    """Save a morning plan and return its ID."""
    with conn.cursor() as cur:
        # Check if plan already exists for today
        cur.execute('''
            SELECT id FROM public.ai_morning_plans 
            WHERE user_id = %(uid)s AND plan_date = %(pdate)s
        ''', {"uid": user_id, "pdate": plan_date})
        existing = cur.fetchone()

        if existing:
            cur.execute('''
                UPDATE public.ai_morning_plans 
                SET mode = %(mode)s, summary = %(sum)s, message = %(msg)s, 
                    total_scheduled_minutes = %(mins)s, overload_risk_score = %(risk)s
                WHERE id = %(id)s
                RETURNING id
            ''', {
                "mode": mode, "sum": summary, "msg": message, "mins": total_minutes, 
                "risk": risk_score, "id": existing[0]
            })
        else:
            cur.execute('''
                INSERT INTO public.ai_morning_plans 
                (user_id, plan_date, mode, summary, message, total_scheduled_minutes, overload_risk_score) 
                VALUES (%(uid)s, %(pdate)s, %(mode)s, %(sum)s, %(msg)s, %(mins)s, %(risk)s)
                RETURNING id
            ''', {
                "uid": user_id, "pdate": plan_date, "mode": mode,
                "sum": summary, "msg": message, "mins": total_minutes, "risk": risk_score
            })
            
        plan_id = cur.fetchone()[0]
    conn.commit()
    return str(plan_id)

def set_morning_plan_recovery_mode(conn: Connection, user_id: str, plan_date: date) -> None:
    """Sets today's morning plan mode to recovery and increases risk score."""
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE public.ai_morning_plans
            SET mode = 'recovery', overload_risk_score = overload_risk_score + 10
            WHERE user_id = %(uid)s AND plan_date = %(pdate)s
        ''', {"uid": user_id, "pdate": plan_date})
    conn.commit()

def get_today_morning_plan(conn: Connection, user_id: str, plan_date: date) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, mode, summary, message, total_scheduled_minutes, overload_risk_score
            FROM public.ai_morning_plans
            WHERE user_id = %(uid)s AND plan_date = %(pdate)s
        ''', {"uid": user_id, "pdate": plan_date})
        result = cur.fetchone()
        return dict(result) if result else None

def get_failed_task_count_last_24h(conn: Connection, user_id: str) -> int:
    """Count deferred or snoozed micro-actions in the last 24 hours."""
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*)
            FROM public.ai_micro_actions
            WHERE user_id = %(uid)s
            AND status IN ('deferred', 'snoozed')
            AND created_at >= NOW() - INTERVAL '1 day'
        ''', {"uid": user_id})
        result = cur.fetchone()
        return result[0] if result else 0

def get_next_open_micro_action(conn: Connection, user_id: str, exclude_high_energy: bool = False) -> Optional[Dict[str, Any]]:
    """Fetch the single next open micro-action for the user, ordered by sort_order."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = '''
            SELECT id, title, description, duration_minutes, energy_cost, status, sort_order, task_id
            FROM public.ai_micro_actions
            WHERE user_id = %(uid)s AND status = 'open'
        '''
        if exclude_high_energy:
            query += " AND energy_cost != 'high'"
            
        query += " ORDER BY sort_order ASC LIMIT 1"
        
        cur.execute(query, {"uid": user_id})
        result = cur.fetchone()
        return dict(result) if result else None

def snooze_high_energy_micro_actions(conn: Connection, user_id: str) -> int:
    """Snooze all open high-energy micro actions for the user."""
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE public.ai_micro_actions
            SET status = 'snoozed'
            WHERE user_id = %(uid)s 
            AND status = 'open' 
            AND energy_cost = 'high'
        ''', {"uid": user_id})
        count = cur.rowcount
    conn.commit()
    return count

def get_plan_micro_actions(conn: Connection, plan_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, title, description, duration_minutes, energy_cost, status, sort_order, task_id
            FROM public.ai_micro_actions
            WHERE plan_id = %(pid)s
            ORDER BY sort_order ASC
        ''', {"pid": plan_id})
        return [dict(row) for row in cur.fetchall()]

def save_reply_draft(conn: Connection, user_id: str, original_message: str, user_intent: str, options: List[Dict[str, Any]], source: str = "llm") -> None:
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO public.ai_reply_drafts 
            (user_id, original_message, user_intent, draft_options, source) 
            VALUES (%(uid)s, %(msg)s, %(int)s, %(opt)s::jsonb, %(src)s)
        ''', {
            "uid": user_id, "msg": original_message, "int": user_intent or "", 
            "opt": json.dumps(options), "src": source
        })
    conn.commit()

def save_transition_script(conn: Connection, user_id: str, transition_type: str, title: str, steps: List[str], source: str = "llm") -> None:
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO public.ai_transition_scripts 
            (user_id, transition_type, title, script_steps, source) 
            VALUES (%(uid)s, %(ttype)s, %(title)s, %(steps)s::jsonb, %(src)s)
        ''', {
            "uid": user_id, "ttype": transition_type, "title": title, 
            "steps": json.dumps(steps), "src": source
        })
    conn.commit()

def get_micro_actions_for_task(conn: Connection, user_id: str, task_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, status, sort_order, task_id, parent_id
            FROM public.ai_micro_actions
            WHERE user_id = %(uid)s AND task_id = %(tid)s
            ORDER BY sort_order ASC
        ''', {"uid": user_id, "tid": task_id})
        return [dict(row) for row in cur.fetchall()]

def delete_open_micro_actions_for_task(conn: Connection, user_id: str, task_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute('''
            DELETE FROM public.ai_micro_actions
            WHERE user_id = %(uid)s AND task_id = %(tid)s AND status = 'open'
        ''', {"uid": user_id, "tid": task_id})
    conn.commit()

def get_micro_action_by_id(conn: Connection, user_id: str, micro_action_id: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''
            SELECT id, title, description, duration_minutes, energy_cost, sensory_cost, friction_level, status, sort_order, task_id, parent_id
            FROM public.ai_micro_actions
            WHERE user_id = %(uid)s AND id = %(maid)s
        ''', {"uid": user_id, "maid": micro_action_id})
        result = cur.fetchone()
        return dict(result) if result else None

def set_micro_action_status(conn: Connection, user_id: str, micro_action_id: str, status: str) -> None:
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE public.ai_micro_actions
            SET status = %(status)s
            WHERE user_id = %(uid)s AND id = %(maid)s
        ''', {"uid": user_id, "maid": micro_action_id, "status": status})
    conn.commit()

def get_max_sort_order(conn: Connection, user_id: str, task_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT MAX(sort_order)
            FROM public.ai_micro_actions
            WHERE user_id = %(uid)s AND task_id = %(tid)s
        ''', {"uid": user_id, "tid": task_id})
        result = cur.fetchone()
        return result[0] if result and result[0] is not None else 0
