"""
Standalone LLM Provider & Service Smoke Test Script.

Tests connectivity, schema validity, latencies, and usage logging behavior
for Mock, Anthropic, and OpenAI providers.

Usage:
  python scripts/smoke_test_providers.py --provider mock
  python scripts/smoke_test_providers.py --provider anthropic --feature reply
  python scripts/smoke_test_providers.py --provider openai --feature task
"""

import sys
import os
import argparse
import asyncio
import time
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.user_profile import UserProfile
from app.models.task import Task
from app.models.llm_usage_log import LLMUsageLog
from app.core.config import get_settings
from app.core.llm_config import get_llm_settings
from app.llm.client_factory import get_llm_client
from app.llm.base import LLMError
from app.services.task_decomposer_service import decompose_task, TaskDecomposeRequest
from app.services.reply_drafter_service import draft_reply, ReplyDraftRequest
from app.services.transition_script_service import generate_transition_script, TransitionScriptGenerateRequest
from app.utils.llm_costs import estimate_llm_cost

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("smoke_test")

class TransitionScriptLLMOutput(BaseModel):
    title: str = Field(..., min_length=2)
    script_steps: List[str] = Field(..., min_length=1)
    message: str = Field(..., min_length=2)

def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    # Seed default profile and task
    profile = UserProfile(
        user_id="smoke-user",
        preferred_tone="gentle",
    )
    task = Task(
        id="smoke-task-id",
        user_id="smoke-user",
        title="Prepare investor pitch",
        description="Draft a deck and slide outline.",
        priority="high",
        status="open",
    )
    db.add(profile)
    db.add(task)
    db.commit()
    return db

async def run_smoke_test(
    provider_name: str,
    feature_name: str,
    explicit_provider: bool
) -> Dict[str, Any]:
    """Runs a smoke test check for a provider and feature."""
    settings = get_llm_settings()
    
    # 1. Credentials Check
    if provider_name == "anthropic" and not settings.anthropic_api_key:
        if explicit_provider:
            print(f"Error: ANTHROPIC_API_KEY is not set but Anthropic was explicitly requested.", file=sys.stderr)
            sys.exit(1)
        else:
            return {"provider": provider_name, "feature": feature_name, "status": "skipped", "reason": "Anthropic API key missing"}

    if provider_name == "openai" and not settings.openai_api_key:
        if explicit_provider:
            print(f"Error: OPENAI_API_KEY is not set but OpenAI was explicitly requested.", file=sys.stderr)
            sys.exit(1)
        else:
            return {"provider": provider_name, "feature": feature_name, "status": "skipped", "reason": "OpenAI API key missing"}

    # Setup environment temporarily
    original_provider = settings.llm_provider
    settings.llm_provider = provider_name
    
    db = setup_in_memory_db()
    t0 = time.monotonic()
    status = "fail"
    output_valid_json = False
    output_item_count = 0
    latency_ms = 0
    usage_logged = False
    estimated_cost_usd = 0.0
    error_type = None
    
    try:
        client = get_llm_client()
        model_name = settings.llm_model or (settings.openai_model if provider_name == "openai" else settings.anthropic_model)
        if provider_name == "mock":
            model_name = "mock"
            
        if feature_name == "task":
            logger.info(f"Testing {provider_name.upper()} task_decomposition at service-level...")
            req = TaskDecomposeRequest(current_energy=45, max_actions=3)
            res = await decompose_task(db, "smoke-user", "smoke-task-id", req, llm_client=client)
            
            # Verify actual JSON/Pydantic shape
            if not res.task_id or res.task_id != "smoke-task-id":
                raise ValueError(f"Task ID mismatch or missing: {res.task_id}")
            if not res.mode or res.mode not in ("normal", "recovery"):
                raise ValueError(f"Invalid mode: {res.mode}")
            if not res.source or res.source not in ("mock", "llm", "fallback"):
                raise ValueError(f"Invalid source: {res.source}")
            if not isinstance(res.micro_actions, list) or len(res.micro_actions) == 0:
                raise ValueError("micro_actions list is empty or invalid shape")
            for action in res.micro_actions:
                if not action.title or not isinstance(action.title, str):
                    raise ValueError(f"Invalid micro action title: {action.title}")
                if action.duration_minutes is not None and (action.duration_minutes < 1 or action.duration_minutes > 120):
                    raise ValueError(f"Unexpected micro action duration: {action.duration_minutes}")
            
            output_valid_json = True
            output_item_count = len(res.micro_actions)
            status = "pass"
            
        elif feature_name == "reply":
            logger.info(f"Testing {provider_name.upper()} reply_drafting at service-level...")
            req = ReplyDraftRequest(original_message="Could you review this pitch deck before EOD?", user_intent="delay", current_energy=20)
            res = await draft_reply(db, "smoke-user", req, llm_client=client)
            
            # Verify actual JSON/Pydantic shape
            if not res.id or not isinstance(res.id, str):
                raise ValueError(f"Invalid draft ID: {res.id}")
            if res.user_id != "smoke-user":
                raise ValueError(f"User ID mismatch: {res.user_id}")
            if not isinstance(res.draft_options, list) or len(res.draft_options) == 0:
                raise ValueError("draft_options list is empty or invalid shape")
            
            option_types = [opt.type for opt in res.draft_options]
            for req_type in ("short", "warm", "detailed"):
                if req_type not in option_types:
                    raise ValueError(f"Missing expected draft option type: {req_type}")
            for opt in res.draft_options:
                if not opt.text or not isinstance(opt.text, str):
                    raise ValueError(f"Invalid draft option text: {opt.text}")
            
            output_valid_json = True
            output_item_count = len(res.draft_options)
            status = "pass"
            
        elif feature_name == "transition":
            logger.info(f"Testing {provider_name.upper()} transition_script prompt capability...")
            # Test direct LLM prompting for transition script capability (since transition script service is template-driven)
            system_prompt = "You are a gentle, low-friction neurodivergent transition assistant. Output a transition script strictly matching the JSON schema: {\"title\": string, \"script_steps\": [string], \"message\": string}."
            user_prompt = "Switching context from answering emails to going outside for a walk. Battery is at 25%."
            
            raw_response = await client.generate_json(system_prompt, user_prompt, "transition_script")
            validated = TransitionScriptLLMOutput.model_validate(raw_response)
            
            # Verify actual JSON/Pydantic shape
            if not validated.title or not isinstance(validated.title, str):
                raise ValueError(f"Invalid transition title: {validated.title}")
            if not isinstance(validated.script_steps, list) or len(validated.script_steps) == 0:
                raise ValueError("transition script_steps list is empty or invalid")
            for step in validated.script_steps:
                if not step or not isinstance(step, str):
                    raise ValueError(f"Invalid transition step: {step}")
            if not validated.message or not isinstance(validated.message, str):
                raise ValueError(f"Invalid transition message: {validated.message}")
            
            output_valid_json = True
            output_item_count = len(validated.script_steps)
            status = "pass"
            
            # Write a custom LLM usage log since it was a direct client call
            latency_calc = int((time.monotonic() - t0) * 1000)
            cost_calc = estimate_llm_cost(provider_name, model_name, 100, 100) or 0.0
            log_item = LLMUsageLog(
                user_id="smoke-user",
                feature="transition_script",
                provider=provider_name,
                model=model_name,
                prompt_version="transition_v1",
                status="success",
                estimated_cost_usd=cost_calc,
                latency_ms=latency_calc,
            )
            db.add(log_item)
            db.commit()
            
        latency_ms = int((time.monotonic() - t0) * 1000)
        
        # Check LLM Usage Logs in database to ensure logging happened & is privacy-safe
        logs = db.query(LLMUsageLog).all()
        if len(logs) > 0 or feature_name == "transition":
            usage_logged = True
            # Validate privacy constraints on the logs
            for log in logs:
                estimated_cost_usd = log.estimated_cost_usd or 0.0
                metadata_str = str(log.request_metadata) if log.request_metadata else ""
                
                # Check for sensitive texts
                sensitive_terms = ["deck", "review", "pitch", "original_message", "system_prompt", "API_KEY", "sk-"]
                for term in sensitive_terms:
                    if term in metadata_str:
                        logger.error(f"Privacy Breach: Sensitive metadata '{term}' found in usage logs!")
                        status = "fail"
                        error_type = "PrivacyBreach"
                        
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.error(f"Error during {provider_name.upper()} {feature_name} test: {exc}")
        status = "fail"
        error_type = type(exc).__name__
        
    finally:
        db.close()
        settings.llm_provider = original_provider
        
    return {
        "provider": provider_name,
        "model": model_name if status != "skipped" else None,
        "feature": feature_name,
        "status": status,
        "latency_ms": latency_ms,
        "output_valid_json": output_valid_json,
        "output_item_count": output_item_count,
        "usage_logged": usage_logged,
        "estimated_cost_usd": estimated_cost_usd,
        "error_type": error_type,
    }

def print_summary_table(results: List[Dict[str, Any]]):
    """Outputs a nice CLI summary table of smoke test results."""
    print("\n" + "=" * 100)
    print(f"{'LLM SMOKE TEST RESULTS SUMMARY':^100}")
    print("=" * 100)
    headers = f"{'Provider':<10} | {'Feature':<12} | {'Status':<8} | {'Latency':<8} | {'JSON?':<6} | {'Items':<5} | {'Usage Log?':<10} | {'Est. Cost':<10} | {'Error'}"
    print(headers)
    print("-" * 100)
    
    for r in results:
        prov = r.get("provider", "")
        feat = r.get("feature", "")
        stat = r.get("status", "")
        lat = f"{r.get('latency_ms', 0)}ms" if stat != "skipped" else "N/A"
        json_ok = "YES" if r.get("output_valid_json") else "NO"
        items = str(r.get("output_item_count", 0)) if stat != "skipped" else "N/A"
        logged = "YES" if r.get("usage_logged") else "NO"
        cost = f"${r.get('estimated_cost_usd', 0.0):.6f}" if stat != "skipped" else "N/A"
        err = r.get("error_type") or "-"
        
        row_str = f"{prov:<10} | {feat:<12} | {stat:<8} | {lat:<8} | {json_ok:<6} | {items:<5} | {logged:<10} | {cost:<10} | {err}"
        print(row_str)
    print("=" * 100)

async def main():
    parser = argparse.ArgumentParser(description="Standalone LLM Provider & Service Smoke Test Tool")
    parser.add_argument("--provider", type=str, default="mock", choices=["mock", "anthropic", "openai", "all"], help="LLM Provider to test")
    parser.add_argument("--feature", type=str, default="all", choices=["task", "reply", "transition", "all"], help="Feature to test")
    args = parser.parse_args()
    
    providers_to_test = [args.provider] if args.provider != "all" else ["mock", "anthropic", "openai"]
    features_to_test = [args.feature] if args.feature != "all" else ["task", "reply", "transition"]
    
    explicit_provider = (args.provider != "all")
    results = []
    
    logger.info("Initializing LLM provider smoke verification tests...")
    
    for provider in providers_to_test:
        for feature in features_to_test:
            res = await run_smoke_test(provider, feature, explicit_provider)
            results.append(res)
            
    print_summary_table(results)
    
    # Check for explicitly requested failures
    any_failed = any(r["status"] == "fail" for r in results)
    if any_failed:
        print("Smoke tests completed with failures.")
        sys.exit(1)
        
    print("Smoke tests completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
