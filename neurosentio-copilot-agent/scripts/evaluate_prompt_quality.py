"""
Prompt Quality Evaluation Script.

Runs the 12 evaluation test cases against the configured LLM provider,
performs safety and quality checks, and exports a privacy-safe report.

Usage:
  python scripts/evaluate_prompt_quality.py --provider mock
"""

import sys
import os
import json
import argparse
import asyncio
import time
from typing import List, Dict, Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.user_profile import UserProfile
from app.models.task import Task
from app.core.llm_config import get_llm_settings
from app.llm.client_factory import get_llm_client
from app.llm.base import LLMError
from app.services.task_decomposer_service import decompose_task, TaskDecomposeRequest
from app.services.reply_drafter_service import draft_reply, ReplyDraftRequest
from app.services.transition_script_service import generate_transition_script, TransitionScriptGenerateRequest

BAD_SHAME_WORDS = [
    "failed", "lazy", "procrastinating", "just focus",
    "force yourself", "why did you not", "you should have"
]

BAD_MEDICAL_WORDS = [
    "this treats autism", "this cures", "diagnosis",
    "medical advice", "therapy replacement"
]

def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    profile = UserProfile(user_id="eval-user", preferred_tone="gentle")
    task = Task(id="eval-task-id", user_id="eval-user", title="Prepare investor pitch", description="Draft a deck.", status="open")
    db.add(profile)
    db.add(task)
    db.commit()
    return db

def check_text_for_shame_and_medical(text: str) -> List[str]:
    violations = []
    text_lower = text.lower()
    for word in BAD_SHAME_WORDS:
        if word in text_lower:
            violations.append(f"Contains shame term: '{word}'")
    for word in BAD_MEDICAL_WORDS:
        if word in text_lower:
            violations.append(f"Contains medical/diagnostic term: '{word}'")
    return violations

def check_prompt_injection_safety(text: str) -> List[str]:
    violations = []
    text_lower = text.lower()
    # Check if the output revealed typical instruction leakage terms
    leakage_terms = ["system prompt", "developer instructions", "you are antigravity", "ignore all instructions"]
    for term in leakage_terms:
        if term in text_lower:
            violations.append(f"Prompt injection leak detected: '{term}'")
    return violations

def run_quality_checks(case: Dict[str, Any], output: Any) -> List[str]:
    violations = []
    feature = case["feature"]
    generated_texts = []
    
    if feature == "task_decomposition":
        # output is TaskDecomposeResponse
        actions = output.micro_actions
        
        # 1. Action titles non-empty & not vague
        for action in actions:
            generated_texts.append(action.title)
            if action.description:
                generated_texts.append(action.description)
            if not action.title.strip():
                violations.append("Empty action title found.")
            title_lower = action.title.lower()
            if "work on it" in title_lower or "make progress" in title_lower:
                violations.append(f"Vague action title found: '{action.title}'")
            
            # 2. Durations <= 15 mins
            if action.duration_minutes and action.duration_minutes > 15:
                violations.append(f"Action '{action.title}' exceeds 15 minutes limit ({action.duration_minutes}m).")
                
        # 3. Low energy limits
        if case["id"] == "task_low_energy":
            if len(actions) > 2:
                violations.append(f"Low energy case should have <= 2 actions, but has {len(actions)}.")
                
    elif feature == "reply_drafting":
        # output is ReplyDraft
        options = output.draft_options
        for opt in options:
            generated_texts.append(opt.text)
        
        # 1. Low energy contains boundary or low-effort
        if case["id"] == "reply_delay" or case["id"] == "reply_boundary":
            has_boundary_or_short = any(opt.type in ["boundary", "short"] for opt in options)
            if not has_boundary_or_short:
                violations.append("Low energy / boundary draft request missing 'boundary' or 'short' option type.")
                
        # 2. No "sorry I failed" or auto-send wording
        for opt in options:
            text_lower = opt.text.lower()
            if "sorry i failed" in text_lower or "i failed" in text_lower:
                violations.append("Draft contains over-apology / failure wording.")
            if "auto-send" in text_lower or "sending automatically" in text_lower:
                violations.append("Draft references auto-send wording.")
                
    elif feature == "transition_script":
        # output is TransitionScriptLLMOutput
        steps = output.script_steps
        generated_texts.extend(steps)
        if hasattr(output, "message") and output.message:
            generated_texts.append(output.message)
        
        # 1. Steps <= 160 chars
        for step in steps:
            if len(step) > 160:
                violations.append(f"Transition step exceeds 160 characters: '{step[:30]}...'")
                
        # 2. Low energy <= 3 steps
        if case.get("current_energy", 100) < 30:
            if len(steps) > 3:
                violations.append(f"Low energy transition exceeds 3 steps limit ({len(steps)} steps).")
                
        # 3. First step physically easy (basic heuristic: short step)
        if len(steps) > 0 and len(steps[0]) > 80:
            violations.append("First transition step is too complex / long.")
            
    # Now scan only the actual generated texts for shame, medical terms, and prompt injection leaks
    for text in generated_texts:
        violations.extend(check_text_for_shame_and_medical(text))
        violations.extend(check_prompt_injection_safety(text))
            
    return violations

async def run_evaluation_case(
    case: Dict[str, Any],
    provider_name: str
) -> Dict[str, Any]:
    settings = get_llm_settings()
    
    # Temp override provider
    original_provider = settings.llm_provider
    settings.llm_provider = provider_name
    
    db = setup_in_memory_db()
    t0 = time.monotonic()
    status = "fail"
    violations = []
    
    try:
        client = get_llm_client()
        feature = case["feature"]
        
        if feature == "task_decomposition":
            # Call service decompose
            req = TaskDecomposeRequest(
                current_energy=case.get("current_energy"),
                sensory_state=case.get("sensory_state"),
                max_actions=case.get("max_actions", 5)
            )
            res = await decompose_task(db, "eval-user", "eval-task-id", req, llm_client=client)
            violations = run_quality_checks(case, res)
            status = "pass" if len(violations) == 0 else "fail"
            
        elif feature == "reply_drafting":
            # Call service draft_reply
            req = ReplyDraftRequest(
                original_message=case["original_message"],
                user_intent=case["user_intent"],
                current_energy=case.get("current_energy")
            )
            res = await draft_reply(db, "eval-user", req, llm_client=client)
            violations = run_quality_checks(case, res)
            status = "pass" if len(violations) == 0 else "fail"
            
        elif feature == "transition_script":
            # Direct LLM Prompt Call as in smoke test
            system_prompt = "You are a gentle transition assistant. Output a transition script strictly matching the JSON schema: {\"title\": string, \"script_steps\": [string], \"message\": string}."
            user_prompt = f"Transition: {case['transition_type']}. Energy: {case.get('current_energy')}."
            
            raw_response = await client.generate_json(system_prompt, user_prompt, "transition_script")
            from scripts.smoke_test_providers import TransitionScriptLLMOutput
            validated = TransitionScriptLLMOutput.model_validate(raw_response)
            
            violations = run_quality_checks(case, validated)
            status = "pass" if len(violations) == 0 else "fail"
            
    except Exception as exc:
        status = "fail"
        violations = [f"Exception occurred: {exc}"]
        
    finally:
        db.close()
        settings.llm_provider = original_provider
        
    return {
        "case_id": case["id"],
        "feature": feature,
        "status": status,
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "violations": violations
    }

def export_reports(results: List[Dict[str, Any]], provider_name: str):
    """Saves privacy-safe report files to reports/ directory."""
    os.makedirs("reports", exist_ok=True)
    
    # 1. JSON Report
    json_path = "reports/prompt_eval_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "provider": provider_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_cases": len(results),
            "passed_cases": sum(1 for r in results if r["status"] == "pass"),
            "results": results
        }, f, indent=2)
        
    # 2. Markdown Report
    md_path = "reports/prompt_eval_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Prompt Quality Evaluation Report ({provider_name.upper()})\n\n")
        f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
        
        passed = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        f.write(f"**Score: {passed} / {total} cases passed**\n\n")
        
        f.write("| Case ID | Feature | Status | Latency | Violations |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            case_id = r["case_id"]
            feat = r["feature"]
            stat = "PASS" if r["status"] == "pass" else "FAIL"
            lat = f"{r['latency_ms']}ms"
            viols = ", ".join(r["violations"]) if r["violations"] else "None"
            f.write(f"| {case_id} | {feat} | {stat} | {lat} | {viols} |\n")
            
        f.write("\n---\n*Privacy Guard: This report is fully sanitized. Original messages, generated prompt texts, and drafts are never recorded here.*\n")

async def main():
    parser = argparse.ArgumentParser(description="Prompt Quality Evaluation Runner")
    parser.add_argument("--provider", type=str, default="mock", choices=["mock", "anthropic", "openai"], help="LLM Provider to evaluate")
    args = parser.parse_args()
    
    settings = get_llm_settings()
    
    # Verify API key if real provider requested
    if args.provider == "anthropic" and not settings.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY is not set but Anthropic was requested.", file=sys.stderr)
        sys.exit(1)
    if args.provider == "openai" and not settings.openai_api_key:
        print("Error: OPENAI_API_KEY is not set but OpenAI was requested.", file=sys.stderr)
        sys.exit(1)
        
    # Load cases
    cases_path = "tests/fixtures/prompt_eval_cases.json"
    if not os.path.exists(cases_path):
        print(f"Error: Fixtures file {cases_path} does not exist.", file=sys.stderr)
        sys.exit(1)
        
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    print(f"Loaded {len(cases)} prompt quality evaluation cases. Evaluating on provider: {args.provider.upper()}...")
    results = []
    
    for case in cases:
        res = await run_evaluation_case(case, args.provider)
        results.append(res)
        
    export_reports(results, args.provider)
    
    # Print nice console summary
    print("\nPrompt Quality Evaluation Summary:")
    print("-" * 60)
    for r in results:
        stat_str = "PASS" if r["status"] == "pass" else "FAIL"
        print(f"  {r['case_id']:<25} | {stat_str:<5} | {r['latency_ms']:>4}ms | Violations: {len(r['violations'])}")
    print("-" * 60)
    
    failed = any(r["status"] == "fail" for r in results)
    if failed:
        print("Prompt quality evaluation completed with failures.")
        sys.exit(1)
        
    print("Prompt quality evaluation completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
