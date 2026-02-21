"""
SIGNAL — Agent 1: Brand Intake Agent
=========================================
Purpose : Onboard a company and produce a structured CompanyProfile.
LLM     : gemini-2.0-flash (fast, cost-efficient structured extraction)
ADK     : Single LLM Agent with two tool calls:
            1. validate_brand_profile  — checks completeness, returns gaps
            2. save_company_profile    — persists the profile to SQLite
Pattern : input → LLM extraction → validation tool → save tool → CompanyProfile
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from typing import Optional

import aiosqlite
from google.adk.agents import Agent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

import backend.database as _db_module
from backend.config import settings
from backend.integrations.braintrust_tracing import TracedRun
from backend.models.company import CompanyProfile, CompanyProfileInput

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Tool definitions (plain Python functions — ADK wraps them)
# ──────────────────────────────────────────────────────────────

def validate_brand_profile(
    name: str,
    industry: str,
    tone_of_voice: str,
    target_audience: str,
    campaign_goals: str,
) -> dict:
    """
    Validate that the extracted brand profile has all required fields.

    Returns a dict with:
      - is_valid (bool): True if all required fields are non-empty
      - missing_fields (list[str]): Names of any empty required fields
      - message (str): Human-readable status
    """
    required = {
        "name": name,
        "industry": industry,
        "tone_of_voice": tone_of_voice,
        "target_audience": target_audience,
        "campaign_goals": campaign_goals,
    }
    missing = [k for k, v in required.items() if not v or not v.strip()]
    is_valid = len(missing) == 0
    return {
        "is_valid": is_valid,
        "missing_fields": missing,
        "message": (
            "Profile is complete and ready to save."
            if is_valid
            else f"Missing required fields: {', '.join(missing)}. Please provide these."
        ),
    }


def save_company_profile(
    name: str,
    industry: str,
    tone_of_voice: str,
    target_audience: str,
    campaign_goals: str,
    competitors: str = "[]",
    content_history: str = "[]",
    visual_style: str = "",
    safety_threshold: float = 0.7,
    website: str = "",
) -> dict:
    """
    Save the validated company profile to the SQLite database.

    Args:
        name: Company name
        industry: Industry vertical
        tone_of_voice: Brand voice style
        target_audience: Primary audience description
        campaign_goals: Marketing objectives
        competitors: JSON array string of competitor names
        content_history: JSON array string of past content examples
        visual_style: Visual identity description
        safety_threshold: Content safety threshold (0.0 - 1.0)
        website: Company website URL (optional)

    Returns:
        dict with company_id and confirmation message.
    """
    # Parse JSON strings safely
    try:
        competitors_list = json.loads(competitors) if competitors else []
    except (json.JSONDecodeError, TypeError):
        competitors_list = [competitors] if competitors else []

    try:
        history_list = json.loads(content_history) if content_history else []
    except (json.JSONDecodeError, TypeError):
        history_list = [content_history] if content_history else []

    profile = CompanyProfile(
        name=name,
        industry=industry,
        website=website.strip() or None,
        tone_of_voice=tone_of_voice,
        target_audience=target_audience,
        campaign_goals=campaign_goals,
        competitors=competitors_list,
        content_history=history_list,
        visual_style=visual_style or None,
        safety_threshold=float(safety_threshold),
    )

    # Run async DB save synchronously (tool functions must be sync for ADK).
    # Use a dedicated thread to avoid "event loop already running" errors when
    # the tool is called from within an async pytest or ADK context.
    _run_async((_persist_profile(profile)))

    return {
        "company_id": profile.id,
        "name": profile.name,
        "message": f"Company profile for '{profile.name}' saved successfully with ID {profile.id}.",
        "profile_summary": {
            "industry": profile.industry,
            "tone": profile.tone_of_voice,
            "audience": profile.target_audience,
            "goals": profile.campaign_goals,
            "competitors_count": len(profile.competitors),
        },
    }


def _run_async(coro) -> None:
    """
    Run a coroutine synchronously, even if an event loop is already running.
    Spawns a worker thread with its own event loop so the tool stays sync
    while remaining safe inside pytest-asyncio / ADK async contexts.
    """
    exc: list = []

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception as e:
            exc.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    if exc:
        raise exc[0]


async def _persist_profile(profile: CompanyProfile) -> None:
    """Write the CompanyProfile to SQLite.
    Reads DB_PATH from the module at call-time so tests can monkeypatch it."""
    db_path = _db_module.DB_PATH
    await _db_module.init_db(db_path)
    row = profile.to_db_row()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO companies
                (id, name, industry, website, tone_of_voice, target_audience,
                 campaign_goals, competitors, content_history, visual_style,
                 safety_threshold, created_at, updated_at)
            VALUES
                (:id, :name, :industry, :website, :tone_of_voice, :target_audience,
                 :campaign_goals, :competitors, :content_history, :visual_style,
                 :safety_threshold, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                industry=excluded.industry,
                website=excluded.website,
                tone_of_voice=excluded.tone_of_voice,
                target_audience=excluded.target_audience,
                campaign_goals=excluded.campaign_goals,
                competitors=excluded.competitors,
                content_history=excluded.content_history,
                visual_style=excluded.visual_style,
                safety_threshold=excluded.safety_threshold,
                updated_at=excluded.updated_at
            """,
            row,
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────
# Agent 1 Definition
# ──────────────────────────────────────────────────────────────

BRAND_INTAKE_INSTRUCTION = """
You are SIGNAL's Brand Intake Agent. Your job is to onboard a new company onto
the SIGNAL platform by extracting a complete, structured brand profile from the
information provided.

## Your Process
1. Read the company information provided in the user message.
2. Extract the following required fields:
   - name: the company's full name
   - industry: the industry vertical (be specific: e.g., "B2B SaaS", "DTC e-commerce")
   - tone_of_voice: the brand's communication style (e.g., "professional and authoritative")
   - target_audience: who they are marketing to (be specific about role/demographic)
   - campaign_goals: their primary marketing objectives
3. Also extract optional fields if present:
   - competitors: a JSON array of competitor names (e.g., ["Competitor A", "Competitor B"])
   - content_history: a JSON array of past content themes or examples
   - visual_style: any visual identity notes
   - website: if a **Website** URL was provided, pass it to save_company_profile
4. ALWAYS call validate_brand_profile first with the extracted fields.
5. If validation passes (is_valid=true), call save_company_profile with ALL extracted data.
6. If validation fails, explain what is missing and ask for clarification.

## Output Format
After saving, summarize the profile you created. Be concise and professional.
Mention the company_id returned by save_company_profile.

## Important Rules
- Never make up information that wasn't provided
- If a field is unclear, use reasonable defaults but flag it
- competitors and content_history must be valid JSON array strings
- safety_threshold default is 0.7 unless specified
"""


def create_brand_intake_agent() -> Agent:
    """Build and return the configured Brand Intake Agent."""
    if not settings.gemini_api_key_set:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Please add it to your .env file.\n"
            "Get a key at: https://aistudio.google.com/apikey"
        )

    return Agent(
        name="brand_intake_agent",
        model="gemini-2.0-flash",
        description="Onboards a company and creates a structured brand profile in SIGNAL.",
        instruction=BRAND_INTAKE_INSTRUCTION,
        tools=[validate_brand_profile, save_company_profile],
    )


# ──────────────────────────────────────────────────────────────
# Public API: run_brand_intake
# ──────────────────────────────────────────────────────────────

async def run_brand_intake(
    intake: CompanyProfileInput,
    session_id: Optional[str] = None,
    website_context: Optional[str] = None,
) -> dict:
    """
    Run the Brand Intake Agent for a given company intake form.

    Args:
        intake: CompanyProfileInput with raw company data
        session_id: Optional session ID for tracing
        website_context: Optional text extracted from company website (merged into agent message)

    Returns:
        dict with:
          - company_id: the saved profile UUID
          - agent_response: full text response from the agent
          - latency_ms: wall-clock time in milliseconds
          - success: bool
    """
    agent = create_brand_intake_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name="signal",
    )

    sid = session_id or str(uuid.uuid4())

    # Build the user message from the intake form (and optional website content)
    user_message = _build_intake_message(intake, website_context=website_context)

    logger.info("Brand Intake Agent starting for company: %s", intake.name)
    start = time.time()

    bt_input = {
        "name": intake.name,
        "industry": intake.industry,
        "tone_of_voice": intake.tone_of_voice,
        "target_audience": intake.target_audience,
        "campaign_goals": intake.campaign_goals,
    }

    # Create session then run
    await session_service.create_session(app_name="signal", user_id="system", session_id=sid)

    full_response = ""
    company_id = None

    with TracedRun("brand_intake", input=bt_input) as bt_span:
        async for event in runner.run_async(
            user_id="system",
            session_id=sid,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_message)],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                full_response = "".join(p.text for p in event.content.parts if hasattr(p, "text"))

        latency_ms = int((time.time() - start) * 1000)

        # Extract company_id from the save tool result stored in session
        if "ID " in full_response:
            for token in full_response.split():
                if len(token) == 36 and token.count("-") == 4:
                    company_id = token.rstrip(".,;")
                    break

        bt_span.log_output(
            output={
                "company_id": company_id,
                "agent_response": full_response[:500] if full_response else "",
                "success": company_id is not None,
            },
            scores={"success": 1.0 if company_id else 0.0},
            metadata={"latency_ms": latency_ms},
        )

    logger.info(
        "Brand Intake Agent completed in %dms. company_id=%s", latency_ms, company_id
    )

    return {
        "company_id": company_id,
        "agent_response": full_response,
        "latency_ms": latency_ms,
        "success": company_id is not None,
    }


def _build_intake_message(intake: CompanyProfileInput, website_context: Optional[str] = None) -> str:
    """Format the CompanyProfileInput into a structured message for the agent."""
    parts = [f"Please onboard the following company onto SIGNAL:\n"]
    parts.append(f"**Company Name**: {intake.name}")
    parts.append(f"**Industry**: {intake.industry}")
    if intake.website:
        parts.append(f"**Website**: {intake.website}")

    if website_context:
        parts.append(f"\n**Content from company website (use this to infer missing fields):**\n{website_context}")

    if intake.tone_of_voice:
        parts.append(f"**Tone of Voice**: {intake.tone_of_voice}")
    if intake.target_audience:
        parts.append(f"**Target Audience**: {intake.target_audience}")
    if intake.campaign_goals:
        parts.append(f"**Campaign Goals**: {intake.campaign_goals}")
    if intake.competitors:
        parts.append(f"**Competitors**: {', '.join(intake.competitors)}")
    if intake.content_history:
        parts.append(f"**Content History**: {'; '.join(intake.content_history)}")
    if intake.visual_style:
        parts.append(f"**Visual Style**: {intake.visual_style}")
    if intake.safety_threshold is not None:
        parts.append(f"**Safety Threshold**: {intake.safety_threshold}")
    if intake.description:
        parts.append(f"\n**Additional Context**: {intake.description}")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────
# CLI entry point for quick manual testing
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)

    sample = CompanyProfileInput(
        name="Acme Analytics",
        industry="B2B SaaS",
        tone_of_voice="professional yet approachable, data-driven",
        target_audience="Data engineers and analytics leads at Series B+ startups",
        campaign_goals="increase free trial signups and reduce time-to-activation",
        competitors=["Tableau", "Looker", "Metabase"],
        content_history=[
            "Thought leadership on data stack modernization",
            "Product walkthroughs for the modern data team",
        ],
        visual_style="clean, minimal, blue/white palette",
    )

    result = asyncio.run(run_brand_intake(sample))
    print("\n=== Brand Intake Agent Result ===")
    print(f"Success      : {result['success']}")
    print(f"Company ID   : {result['company_id']}")
    print(f"Latency      : {result['latency_ms']}ms")
    print(f"\nAgent Response:\n{result['agent_response']}")
