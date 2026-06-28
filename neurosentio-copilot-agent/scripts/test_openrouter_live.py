"""
Live integration test for OpenRouter LLM client.

Validates:
  1. Factory correctly creates an OpenRouterClient
  2. Raw JSON generation works against the live API
  3. Task decomposition prompt returns valid micro-actions
  4. Reply draft prompt returns valid draft options
  5. Error handling (bad model, empty prompt)

Usage:
    cd neurosentio-copilot-agent
    python -m scripts.test_openrouter_live
"""

import sys
import io
# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Force .env to load before pydantic-settings caches
from dotenv import load_dotenv
load_dotenv(project_root / ".env", override=True)


# ── Colours for terminal output ──────────────────────────────────────
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def header(title: str):
    print(f"\n{C.CYAN}{C.BOLD}{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}{C.RESET}\n")


def passed(name: str, detail: str = ""):
    print(f"  {C.GREEN}✓ PASS{C.RESET}  {name}  {C.DIM}{detail}{C.RESET}")


def failed(name: str, detail: str = ""):
    print(f"  {C.RED}✗ FAIL{C.RESET}  {name}  {C.DIM}{detail}{C.RESET}")


def info(msg: str):
    print(f"  {C.YELLOW}ℹ{C.RESET}  {msg}")


results: list[dict] = []


def record(name: str, ok: bool, detail: str = "", duration_ms: float = 0):
    results.append({"name": name, "ok": ok, "detail": detail, "ms": duration_ms})
    if ok:
        passed(name, f"({duration_ms:.0f}ms) {detail}")
    else:
        failed(name, detail)


# ─────────────────────────────────────────────────────────────────────
# Test 1: Factory wiring
# ─────────────────────────────────────────────────────────────────────
def test_factory_wiring():
    header("Test 1 — Factory creates OpenRouterClient")
    from app.llm.client_factory import get_llm_client
    from app.llm.openrouter_client import OpenRouterClient
    from app.core.llm_config import get_llm_settings

    # Clear the lru_cache so we pick up fresh .env values
    get_llm_settings.cache_clear()

    settings = get_llm_settings()
    info(f"LLM_PROVIDER = {settings.llm_provider}")
    info(f"OPENROUTER_API_KEY = {settings.openrouter_api_key[:12]}...{settings.openrouter_api_key[-4:]}")
    info(f"Model = {settings.openrouter_model}")

    try:
        client = get_llm_client()
        is_correct = isinstance(client, OpenRouterClient)
        record("Factory returns OpenRouterClient", is_correct,
               f"Got {type(client).__name__}")
    except Exception as e:
        record("Factory returns OpenRouterClient", False, str(e))


# ─────────────────────────────────────────────────────────────────────
# Test 2: Raw JSON generation
# ─────────────────────────────────────────────────────────────────────
async def test_raw_json_generation():
    header("Test 2 — Raw JSON generation (simple prompt)")
    from app.llm.client_factory import get_llm_client
    from app.core.llm_config import get_llm_settings
    get_llm_settings.cache_clear()

    client = get_llm_client()

    system_prompt = (
        "You are a helpful assistant. Always respond with valid JSON.\n\n"
        "Return JSON matching this schema:\n"
        "{\n"
        '  "greeting": "string greeting",\n'
        '  "mood": "string mood",\n'
        '  "confidence": 95\n'
        "}"
    )
    user_prompt = "Say hello to a developer testing an API integration."

    t0 = time.perf_counter()
    try:
        result = await client.generate_json(system_prompt, user_prompt, "test_greeting")
        elapsed = (time.perf_counter() - t0) * 1000

        info(f"Response: {json.dumps(result, indent=2)}")

        has_greeting = isinstance(result.get("greeting"), str) and len(result["greeting"]) > 0
        has_mood = isinstance(result.get("mood"), str)
        has_confidence = isinstance(result.get("confidence"), (int, float))

        record("Response is valid JSON dict", isinstance(result, dict), "", elapsed)
        record("Has 'greeting' field", has_greeting,
               result.get("greeting", "MISSING")[:60] if has_greeting else "")
        record("Has 'mood' field", has_mood,
               result.get("mood", "MISSING"))
        record("Has 'confidence' field", has_confidence,
               str(result.get("confidence", "MISSING")))
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        record("Raw JSON generation", False, str(e), elapsed)


# ─────────────────────────────────────────────────────────────────────
# Test 3: Task decomposition (mimics the real service prompt)
# ─────────────────────────────────────────────────────────────────────
async def test_task_decomposition():
    header("Test 3 — Task decomposition prompt (real service scenario)")
    from app.llm.client_factory import get_llm_client
    from app.core.llm_config import get_llm_settings
    get_llm_settings.cache_clear()

    client = get_llm_client()

    system_prompt = """You are NeuroSentio's task decomposer.
Break a task into 3-5 tiny, neurodivergent-friendly micro-actions.

Return JSON matching this schema:
{
  "micro_actions": [
    {
      "title": "short action title",
      "description": "one-sentence explanation",
      "duration_minutes": 2,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "low"
    }
  ]
}

Rules:
- Each micro-action should be completable in 2-10 minutes.
- energy_cost, sensory_cost, friction_level must be one of: low, medium, high.
- Start with the lowest-friction step to reduce initiation resistance.
- Make the first step trivially easy (opening a file, reading one paragraph)."""

    user_prompt = (
        "Task: 'Write a project README'\n"
        "Priority: medium\n"
        "Current energy: 55/100 (moderate)\n"
        "Mode: normal"
    )

    t0 = time.perf_counter()
    try:
        result = await client.generate_json(system_prompt, user_prompt, "TaskDecomposeResponse")
        elapsed = (time.perf_counter() - t0) * 1000

        info(f"Response: {json.dumps(result, indent=2)}")

        actions = result.get("micro_actions", [])
        record("Returns micro_actions array", isinstance(actions, list) and len(actions) > 0,
               f"{len(actions)} actions", elapsed)

        if actions:
            first = actions[0]
            has_title = isinstance(first.get("title"), str)
            has_desc = isinstance(first.get("description"), str)
            has_duration = isinstance(first.get("duration_minutes"), (int, float))
            valid_energy = first.get("energy_cost") in ("low", "medium", "high")
            valid_sensory = first.get("sensory_cost") in ("low", "medium", "high")
            valid_friction = first.get("friction_level") in ("low", "medium", "high")

            record("First action has title", has_title, first.get("title", "")[:50])
            record("First action has description", has_desc, first.get("description", "")[:50])
            record("First action has duration_minutes", has_duration, str(first.get("duration_minutes")))
            record("Valid energy_cost enum", valid_energy, first.get("energy_cost", "MISSING"))
            record("Valid sensory_cost enum", valid_sensory, first.get("sensory_cost", "MISSING"))
            record("Valid friction_level enum", valid_friction, first.get("friction_level", "MISSING"))
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        record("Task decomposition", False, str(e), elapsed)


# ─────────────────────────────────────────────────────────────────────
# Test 4: Reply draft (mimics the reply drafter service)
# ─────────────────────────────────────────────────────────────────────
async def test_reply_draft():
    header("Test 4 — Reply draft prompt (real service scenario)")
    from app.llm.client_factory import get_llm_client
    from app.core.llm_config import get_llm_settings
    get_llm_settings.cache_clear()

    client = get_llm_client()

    system_prompt = """You are NeuroSentio's reply drafter.
Generate 2-3 reply options for a message. Each reply should have a different tone.

Return JSON matching this schema:
{
  "drafts": [
    {
      "tone": "friendly" | "professional" | "brief",
      "body": "the draft reply text",
      "confidence": 0.85
    }
  ]
}

Rules:
- Keep replies concise (1-3 sentences).
- Include at least a friendly and a professional option.
- confidence is a float 0.0-1.0 representing how appropriate the reply is."""

    user_prompt = (
        "Message from: Team Lead\n"
        "Content: 'Hey, can you send over the progress report by end of day?'\n"
        "Context: User has moderate energy, 3 open tasks, mid-afternoon."
    )

    t0 = time.perf_counter()
    try:
        result = await client.generate_json(system_prompt, user_prompt, "reply_draft")
        elapsed = (time.perf_counter() - t0) * 1000

        info(f"Response: {json.dumps(result, indent=2)}")

        drafts = result.get("drafts", [])
        record("Returns drafts array", isinstance(drafts, list) and len(drafts) >= 2,
               f"{len(drafts)} drafts", elapsed)

        if drafts:
            tones = [d.get("tone") for d in drafts]
            record("Has varied tones", len(set(tones)) > 1, str(tones))

            for i, draft in enumerate(drafts):
                has_body = isinstance(draft.get("body"), str) and len(draft["body"]) > 5
                has_conf = isinstance(draft.get("confidence"), (int, float))
                record(f"Draft {i+1} has body", has_body, draft.get("body", "")[:50])
                record(f"Draft {i+1} has confidence", has_conf, str(draft.get("confidence", "MISSING")))
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        record("Reply draft", False, str(e), elapsed)


# ─────────────────────────────────────────────────────────────────────
# Test 5: Error handling — bad model name
# ─────────────────────────────────────────────────────────────────────
async def test_error_handling():
    header("Test 5 — Error handling (bad model name)")
    from app.llm.openrouter_client import OpenRouterClient
    from app.llm.base import LLMError
    from app.core.llm_config import get_llm_settings
    get_llm_settings.cache_clear()

    settings = get_llm_settings()
    bad_client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model="nonexistent/model-v999",
        timeout=10,
    )

    t0 = time.perf_counter()
    try:
        await bad_client.generate_json("System", "Hello", "test_error")
        elapsed = (time.perf_counter() - t0) * 1000
        record("Bad model raises LLMError", False, "No exception raised", elapsed)
    except LLMError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        record("Bad model raises LLMError", True, str(e)[:80], elapsed)
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        record("Bad model raises LLMError", False, f"Wrong exception: {type(e).__name__}: {e}", elapsed)


# ─────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────
def print_summary():
    header("Summary")
    total = len(results)
    passed_count = sum(1 for r in results if r["ok"])
    failed_count = total - passed_count

    for r in results:
        status = f"{C.GREEN}PASS{C.RESET}" if r["ok"] else f"{C.RED}FAIL{C.RESET}"
        print(f"  {status}  {r['name']}")

    print(f"\n  {C.BOLD}Total: {total}  |  "
          f"{C.GREEN}Passed: {passed_count}{C.RESET}  |  "
          f"{C.RED}Failed: {failed_count}{C.RESET}")

    if failed_count == 0:
        print(f"\n  {C.GREEN}{C.BOLD}🎉 All tests passed! OpenRouter integration is working.{C.RESET}")
    else:
        print(f"\n  {C.RED}{C.BOLD}⚠  Some tests failed. Check the output above.{C.RESET}")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
async def main():
    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║    NeuroSentio — OpenRouter Live Integration Test       ║")
    print(f"╚══════════════════════════════════════════════════════════╝{C.RESET}")

    test_factory_wiring()
    await test_raw_json_generation()
    await test_task_decomposition()
    await test_reply_draft()
    await test_error_handling()
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
