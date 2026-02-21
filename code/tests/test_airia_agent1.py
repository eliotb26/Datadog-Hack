"""
SIGNAL - Airia Agent 1 (Brand Intake) Live Test
=================================================
Tests Agent 1 (Brand Intake) and its Battleground variant independently.

GUIDs:
  Agent 1 main       : ade7cfe7-c80a-454e-ad0a-e036338b2911
  Agent 1 battleground: 1af2a8e4-ef61-4aa4-8c7b-c2c9e9205884

Run:
    python code/tests/test_airia_agent1.py
"""
import json
import os
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root / "code"))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from backend.integrations.airia_client import AiriaClient

# ---------------------------------------------------------------
# Hardcoded GUIDs (confirmed from Airia Studio)
# ---------------------------------------------------------------
AGENT1_GUID       = "ade7cfe7-c80a-454e-ad0a-e036338b2911"
BATTLEGROUND_GUID = "1af2a8e4-ef61-4aa4-8c7b-c2c9e9205884"
API_BASE          = "https://api.airia.ai"

# ---------------------------------------------------------------
# Test payloads — three different company onboarding scenarios
# ---------------------------------------------------------------

FINTECH_INPUT = """Please onboard this company onto SIGNAL:
Company Name: CryptoPay
Industry: Fintech / Crypto Payments
Tone of Voice: bold, authoritative, slightly irreverent
Target Audience: crypto-native millennials and tech-forward finance professionals
Campaign Goals: drive app downloads and grow active wallet users
Competitors: Coinbase, Binance, Strike
Visual Style: dark mode, neon green accents, minimalist"""

SAAS_INPUT = """Please onboard this company onto SIGNAL:
Company Name: NovaTech
Industry: SaaS / Developer Tools
Tone of Voice: technical, bold, slightly witty
Target Audience: software engineers and CTOs at Series B+ startups
Campaign Goals: grow developer community and drive free trial signups
Competitors: GitHub Copilot, Cursor, Tabnine
Content History: Thought leadership on AI-assisted coding; Product walkthroughs for modern dev teams
Visual Style: dark mode, code-forward, minimal"""

HEALTHTECH_INPUT = """Please onboard this company onto SIGNAL:
Company Name: WellPath AI
Industry: HealthTech / Digital Wellness
Tone of Voice: warm, empathetic, science-backed
Target Audience: health-conscious adults 25-45 seeking preventative care
Campaign Goals: increase app subscriptions and build trust with clinical credibility
Competitors: Noom, Calm, MyFitnessPal"""


# ---------------------------------------------------------------
# Helper
# ---------------------------------------------------------------

def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _safe_print(text: str) -> None:
    """Print text safely on Windows cp1252 terminals by replacing unmappable chars."""
    safe = text.encode("cp1252", errors="replace").decode("cp1252")
    print(safe)


def _call_agent(client: AiriaClient, pipeline_id: str, user_input: str, label: str) -> dict:
    _safe_print(f"\n  Calling: {label}")
    _safe_print(f"  GUID   : {pipeline_id}")
    _safe_print(f"  Input  : {user_input[:80].strip()}...")

    result = client.run_pipeline(
        pipeline_id=pipeline_id,
        user_input=user_input,
        async_output=False,
    )

    output = result.get("pipelineOutput", result.get("output", str(result)))
    latency = result.get("latency_ms", "N/A")

    _safe_print(f"\n  Latency: {latency}ms")
    _safe_print("  Output :\n")

    # Pretty-print if JSON, else plain text
    try:
        parsed = json.loads(output) if isinstance(output, str) else output
        _safe_print(json.dumps(parsed, indent=4, ensure_ascii=False))
    except (json.JSONDecodeError, TypeError):
        _safe_print(f"  {output}")

    return result


# ---------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------

def run_tests():
    _divider("SIGNAL - Airia Agent 1 + Battleground Live Test")
    api_key = os.getenv("AIRIA_API_KEY", "")
    print(f"  API Key : {api_key[:16]}...{api_key[-6:]}")
    print(f"  Base URL: {API_BASE}")

    client = AiriaClient(base_url=API_BASE)
    passed = 0
    failed = 0

    # ── Test 1: Agent 1 — Fintech company onboarding ────────────
    _divider("Test 1: Agent 1 (Brand Intake) - Fintech Company")
    try:
        _call_agent(client, AGENT1_GUID, FINTECH_INPUT, "Agent 1 (Brand Intake) - Fintech")
        _safe_print("\n  [PASS] Agent 1 responded successfully")
        passed += 1
    except Exception as e:
        _safe_print(f"\n  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    time.sleep(1)

    # ── Test 2: Agent 1 — SaaS company onboarding ───────────────
    _divider("Test 2: Agent 1 (Brand Intake) - SaaS Company")
    try:
        _call_agent(client, AGENT1_GUID, SAAS_INPUT, "Agent 1 (Brand Intake) - SaaS")
        _safe_print("\n  [PASS] Agent 1 responded successfully")
        passed += 1
    except Exception as e:
        _safe_print(f"\n  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    time.sleep(1)

    # ── Test 3: Agent 1 — HealthTech company onboarding ─────────
    _divider("Test 3: Agent 1 (Brand Intake) - HealthTech Company")
    try:
        _call_agent(client, AGENT1_GUID, HEALTHTECH_INPUT, "Agent 1 (Brand Intake) - HealthTech")
        _safe_print("\n  [PASS] Agent 1 responded successfully")
        passed += 1
    except Exception as e:
        _safe_print(f"\n  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    time.sleep(1)

    # ── Test 4: Battleground — same Fintech input, different agent ──
    _divider("Test 4: Battleground Variant - Fintech Company (A/B Compare)")
    try:
        _call_agent(client, BATTLEGROUND_GUID, FINTECH_INPUT, "Battleground Variant - Fintech")
        _safe_print("\n  [PASS] Battleground agent responded successfully")
        passed += 1
    except Exception as e:
        _safe_print(f"\n  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    time.sleep(1)

    # ── Test 5: Battleground — same SaaS input, side-by-side comparison ──
    _divider("Test 5: Battleground Variant - SaaS Company (A/B Compare)")
    try:
        _call_agent(client, BATTLEGROUND_GUID, SAAS_INPUT, "Battleground Variant - SaaS")
        _safe_print("\n  [PASS] Battleground agent responded successfully")
        passed += 1
    except Exception as e:
        _safe_print(f"\n  [FAIL] {type(e).__name__}: {e}")
        failed += 1

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed} passed | {failed} failed")
    if failed == 0:
        print("  All tests passed - both agents are live and responding!")
    else:
        print("  Some tests failed - check output above for details.")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
