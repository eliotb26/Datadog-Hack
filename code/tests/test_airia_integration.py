"""
SIGNAL - Airia Integration Test (Standalone)
=============================================
Tests the Airia integration independently:
  1. API key is loaded correctly
  2. Airia API is reachable (connectivity check)
  3. Authentication is valid (key is accepted)
  4. AiriaGateway shows which pipelines are/aren't configured
  5. (Optional) Live pipeline execution - if AIRIA_PIPELINE_BRAND_INTAKE is set

Run this directly:
    python code/tests/test_airia_integration.py

Or via pytest:
    pytest code/tests/test_airia_integration.py -v
"""
import os
import sys
from pathlib import Path

# Make sure we can import the backend from any working directory
_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root / "code"))

# Load .env from repo root
from dotenv import load_dotenv
load_dotenv(_root / ".env")

import pytest
from backend.integrations.airia_client import (
    AiriaClient,
    AiriaGateway,
    AiriaNotConfiguredError,
)
from backend.config import settings


# ---------------------------------------------------------------
# Helper: print a clearly formatted test banner
# ---------------------------------------------------------------

def _banner(title: str) -> None:
    print(f"\n{'-' * 55}")
    print(f"  {title}")
    print(f"{'-' * 55}")


# ---------------------------------------------------------------
# Test 1 - API key is present and non-placeholder
# ---------------------------------------------------------------

def test_airia_api_key_configured():
    """AIRIA_API_KEY must be set and non-placeholder."""
    _banner("Test 1: API Key Check")
    key = settings.AIRIA_API_KEY
    print(f"  AIRIA_API_KEY = {key[:12]}...{key[-6:] if len(key) > 18 else '(short)'}")
    print(f"  settings.airia_configured = {settings.airia_configured}")

    assert key, "AIRIA_API_KEY is empty - set it in your .env file."
    assert key != "your_airia_api_key_here", "AIRIA_API_KEY is still the placeholder value."
    assert settings.airia_configured, "settings.airia_configured returned False."
    print("  [PASS] API key looks valid")


# ---------------------------------------------------------------
# Test 2 - AiriaClient can be instantiated
# ---------------------------------------------------------------

def test_airia_client_instantiation():
    """AiriaClient should initialise without errors when key is present."""
    _banner("Test 2: Client Instantiation")
    client = AiriaClient()
    assert client.api_key.startswith("ak-"), (
        f"API key format unexpected (should start with 'ak-'): {client.api_key[:20]}"
    )
    print(f"  [PASS] AiriaClient created. Key prefix: {client.api_key[:12]}...")


# ---------------------------------------------------------------
# Test 3 - Connectivity + auth check (live HTTP call)
# ---------------------------------------------------------------

def test_airia_connectivity():
    """Hit the Airia API to confirm the key is accepted and the API is reachable."""
    _banner("Test 3: Connectivity & Auth Check (live HTTP)")
    client = AiriaClient()
    result = client.test_connectivity()

    print(f"  Connected    : {result['connected']}")
    print(f"  Auth Valid   : {result['auth_valid']}")
    print(f"  Status Code  : {result['status_code']}")
    print(f"  Latency      : {result['latency_ms']}ms")
    print(f"  Message      : {result['message']}")

    assert result["connected"], f"Cannot reach Airia API: {result['message']}"
    assert result["auth_valid"], (
        f"Airia rejected the API key ({result['status_code']}): {result['message']}"
    )
    print("  [PASS] Connected and authenticated!")


# ---------------------------------------------------------------
# Test 4 - AiriaGateway pipeline configuration status
# ---------------------------------------------------------------

def test_airia_gateway_pipeline_status():
    """
    AiriaGateway.configured_agents() should show which pipelines are ready.
    At this stage (before Airia Studio setup) all will be False - that is expected.
    """
    _banner("Test 4: Gateway Pipeline Configuration Status")
    gw = AiriaGateway()
    status = gw.configured_agents()

    print("  Pipeline GUID configuration status:")
    for agent, is_configured in status.items():
        icon = "[SET]" if is_configured else "[---]"
        env_var = AiriaGateway.AGENT_ENV_MAP[agent]
        print(f"    {icon} {agent:<20} -> {env_var}")

    configured_count = sum(status.values())
    print(f"\n  {configured_count}/{len(status)} pipelines configured.")
    if configured_count == 0:
        print(
            "\n  NOTE: No Airia pipelines configured yet - this is expected!\n"
            "  Next step: Create agents in Airia Studio and paste the GUIDs into .env:\n"
            "    AIRIA_PIPELINE_BRAND_INTAKE=<guid>\n"
            "    AIRIA_PIPELINE_TREND_INTEL=<guid>\n"
            "    AIRIA_PIPELINE_CAMPAIGN_GEN=<guid>\n"
            "    AIRIA_PIPELINE_DISTRIBUTION=<guid>\n"
            "    AIRIA_PIPELINE_FEEDBACK_LOOP=<guid>"
        )
    assert isinstance(status, dict)
    assert set(status.keys()) == set(AiriaGateway.AGENT_ENV_MAP.keys())
    print("  [PASS] Gateway config check complete")


# ---------------------------------------------------------------
# Test 5 - Graceful error when calling unconfigured pipeline
# ---------------------------------------------------------------

def test_airia_gateway_raises_when_not_configured():
    """
    Calling run_agent() without a pipeline GUID must raise AiriaNotConfiguredError
    with a helpful message - never a silent failure.
    """
    _banner("Test 5: Graceful Error for Unconfigured Pipeline")
    gw = AiriaGateway()

    # Temporarily ensure the env var is not set for this test
    os.environ.pop("AIRIA_PIPELINE_BRAND_INTAKE", None)

    try:
        gw.run_agent("brand_intake", "test input")
        assert False, "Should have raised AiriaNotConfiguredError"
    except AiriaNotConfiguredError as e:
        print(f"  [PASS] Caught AiriaNotConfiguredError as expected:")
        print(f"    {e}")


# ---------------------------------------------------------------
# Test 6 (Optional) - Live pipeline execution
# Only runs if AIRIA_PIPELINE_BRAND_INTAKE is set in .env
# ---------------------------------------------------------------

def test_airia_live_pipeline_execution():
    """
    If AIRIA_PIPELINE_BRAND_INTAKE is set, run a live call through Airia Studio.
    Skips automatically if the pipeline GUID is not configured.
    """
    _banner("Test 6: Live Pipeline Execution (optional)")
    gw = AiriaGateway()
    pipeline_id = gw.get_pipeline_id("brand_intake")

    if not pipeline_id:
        print("  SKIPPED - AIRIA_PIPELINE_BRAND_INTAKE not set.")
        print("  Set this env var after creating an agent in Airia Studio to enable this test.")
        pytest.skip("AIRIA_PIPELINE_BRAND_INTAKE not configured")

    print(f"  Pipeline GUID: {pipeline_id}")
    print("  Sending test input to Airia...")

    result = gw.run_agent(
        "brand_intake",
        user_input=(
            "Onboard a test company: Name=TestCorp, Industry=SaaS, "
            "Tone=professional, Audience=developers, Goals=grow trial signups."
        ),
    )

    print(f"  Latency      : {result.get('latency_ms', 'N/A')}ms")
    print(f"  Output       : {str(result.get('pipelineOutput', ''))[:200]}")
    assert "pipelineOutput" in result, f"Expected 'pipelineOutput' in response, got: {result}"
    print("  [PASS] Live pipeline call succeeded!")


# ---------------------------------------------------------------
# CLI entry point - run directly with python
# ---------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  SIGNAL - Airia Integration Test Suite")
    print("=" * 55)

    tests = [
        ("API Key Check",               test_airia_api_key_configured),
        ("Client Instantiation",        test_airia_client_instantiation),
        ("Connectivity & Auth",         test_airia_connectivity),
        ("Gateway Pipeline Status",     test_airia_gateway_pipeline_status),
        ("Graceful Unconfigured Error", test_airia_gateway_raises_when_not_configured),
        ("Live Pipeline Execution",     test_airia_live_pipeline_execution),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except pytest.skip.Exception:
            skipped += 1
            print(f"  [SKIP] {name}")
        except AssertionError as e:
            print(f"\n  [FAIL] {name}")
            print(f"    {e}")
            failed += 1
        except Exception as e:
            print(f"\n  [ERROR] {name}")
            print(f"    {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 55}")
    print(f"  Results: {passed} passed | {failed} failed | {skipped} skipped")
    print("=" * 55)

    if failed:
        sys.exit(1)
