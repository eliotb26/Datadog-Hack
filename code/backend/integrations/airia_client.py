"""
onlyGen — Airia Enterprise Orchestration Client
================================================
Purpose : Wraps the Airia Python SDK for onlyGen pipeline execution.

Airia provides:
  - AI Gateway : Intelligent model routing (Gemini Flash vs Pro)
  - Battleground: A/B test different prompt strategies per agent
  - Agent Studio: Visual workflow builder for the 5-agent pipeline
  - Agent Constraints: Policy engine for brand safety rules

Integration pattern:
  - Each onlyGen agent (1-5) can be routed through an Airia pipeline
  - Airia's AI Gateway selects the right model (Flash for speed, Pro for quality)
  - Battleground A/B tests prompt strategies and reports winners
  - Results are traced via Braintrust for the self-improvement loop

Docs: https://explore.airia.com/building-and-deploying-agents/interface-options/api-deployment
SDK : https://airiallc.github.io/airia-python/
API : https://api.airia.ai/docs
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

# Walk up from this file to find .env at any ancestor directory
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate, override=False)
        break
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Airia API constants
AIRIA_BASE_URL = "https://api.airia.ai"
AIRIA_PIPELINE_EXEC_PATH = "/v1/PipelineExecution"


class AiriaError(Exception):
    """Raised when an Airia API call fails."""


class AiriaNotConfiguredError(AiriaError):
    """Raised when AIRIA_API_KEY is missing or AIRIA_PIPELINE_URL is not set."""


class AiriaClient:
    """
    Synchronous client for calling Airia-hosted agent pipelines.

    Usage (once you have a pipeline GUID from Airia Studio):

        client = AiriaClient()
        result = client.run_pipeline(
            pipeline_id="your-pipeline-guid-here",
            user_input="Generate a campaign for a fintech company about rising Bitcoin prices.",
            async_output=False,
        )
        print(result["pipelineOutput"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = AIRIA_BASE_URL,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("AIRIA_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if not self.api_key:
            raise AiriaNotConfiguredError(
                "AIRIA_API_KEY is not set. Add it to your .env file.\n"
                "Get a key at: https://airia.com → Settings → API Keys"
            )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    def run_pipeline(
        self,
        pipeline_id: str,
        user_input: str,
        async_output: bool = False,
        extra_fields: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute an Airia pipeline by its GUID.

        Args:
            pipeline_id   : The pipeline GUID from Airia Studio → Settings → Interfaces → View API Info.
            user_input    : The text prompt / user message to send to the pipeline.
            async_output  : False = wait for the full response (default).
                            True  = fire-and-forget (returns immediately, poll separately).
            extra_fields  : Optional additional body fields (e.g. {"conversationId": "..."}).

        Returns:
            dict with at minimum:
                - pipelineOutput (str): The pipeline's text response
                - latency_ms (int): Wall-clock time for the API call

        Raises:
            AiriaError: On HTTP errors or unexpected responses.
        """
        url = f"{self.base_url}{AIRIA_PIPELINE_EXEC_PATH}/{pipeline_id}"
        payload: dict[str, Any] = {
            "userInput": user_input,
            "asyncOutput": async_output,
        }
        if extra_fields:
            payload.update(extra_fields)

        logger.info(
            "airia_pipeline_call_start",
            extra={"pipeline_id": pipeline_id, "input_len": len(user_input)},
        )
        start = time.perf_counter()

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            if response.status_code == 401:
                raise AiriaError(
                    f"Authentication failed (401). Check your AIRIA_API_KEY. "
                    f"Response: {response.text[:200]}"
                )
            if response.status_code == 404:
                raise AiriaError(
                    f"Pipeline not found (404). Check your pipeline GUID: '{pipeline_id}'. "
                    "Make sure the agent has an Active version published in Airia Studio."
                )
            if not response.ok:
                raise AiriaError(
                    f"Airia API error {response.status_code}: {response.text[:500]}"
                )

            data = response.json()
            data["latency_ms"] = latency_ms
            logger.info(
                "airia_pipeline_call_complete",
                extra={"pipeline_id": pipeline_id, "latency_ms": latency_ms},
            )
            return data

        except requests.exceptions.ConnectionError as exc:
            raise AiriaError(f"Connection error reaching Airia API: {exc}") from exc
        except requests.exceptions.Timeout:
            raise AiriaError(
                f"Airia API timed out after {self.timeout}s for pipeline '{pipeline_id}'."
            )

    def test_connectivity(self) -> dict[str, Any]:
        """
        Test that the API key is valid and the Airia API is reachable.

        Returns:
            dict with:
              - connected (bool)
              - auth_valid (bool)
              - status_code (int)
              - latency_ms (int)
              - message (str)
        """
        # The pipeline execution endpoint returns 404 when no pipeline ID is given,
        # but 401 if the key is wrong — perfect for a connectivity/auth check.
        url = f"{self.base_url}{AIRIA_PIPELINE_EXEC_PATH}/connectivity-check"
        start = time.perf_counter()

        try:
            response = requests.post(
                url,
                json={"userInput": "ping", "asyncOutput": False},
                headers=self._headers,
                timeout=15,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            # 404 → API is reachable and key is valid (pipeline just doesn't exist)
            # 401/403 → key is invalid
            auth_valid = response.status_code not in (401, 403)
            connected = response.status_code != 0

            return {
                "connected": connected,
                "auth_valid": auth_valid,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "message": (
                    "API key valid — Airia API reachable. Ready to execute pipelines."
                    if auth_valid
                    else f"Authentication failed ({response.status_code}). Check AIRIA_API_KEY."
                ),
            }

        except requests.exceptions.ConnectionError as exc:
            return {
                "connected": False,
                "auth_valid": False,
                "status_code": 0,
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "message": f"Cannot reach Airia API: {exc}",
            }
        except requests.exceptions.Timeout:
            return {
                "connected": False,
                "auth_valid": False,
                "status_code": 0,
                "latency_ms": 15000,
                "message": "Airia API timed out during connectivity check.",
            }


class AiriaGateway:
    """
    Convenience wrapper around AiriaClient that maps onlyGen's 5 agents
    to their corresponding Airia pipeline GUIDs (configured via env vars).

    Once you create agents in Airia Studio, set these env vars:
        AIRIA_PIPELINE_BRAND_INTAKE=<guid>
        AIRIA_PIPELINE_TREND_INTEL=<guid>
        AIRIA_PIPELINE_CAMPAIGN_GEN=<guid>
        AIRIA_PIPELINE_DISTRIBUTION=<guid>
        AIRIA_PIPELINE_FEEDBACK_LOOP=<guid>

    Then each agent can call AiriaGateway().run_agent(agent_name, user_input).
    """

    AGENT_ENV_MAP: dict[str, str] = {
        "brand_intake":   "AIRIA_PIPELINE_BRAND_INTAKE",
        "trend_intel":    "AIRIA_PIPELINE_TREND_INTEL",
        "campaign_gen":   "AIRIA_PIPELINE_CAMPAIGN_GEN",
        "distribution":   "AIRIA_PIPELINE_DISTRIBUTION",
        "feedback_loop":  "AIRIA_PIPELINE_FEEDBACK_LOOP",
    }

    def __init__(self) -> None:
        self.client = AiriaClient()

    def get_pipeline_id(self, agent_name: str) -> Optional[str]:
        """Return the Airia pipeline GUID for the given onlyGen agent, or None if not set."""
        env_var = self.AGENT_ENV_MAP.get(agent_name)
        if not env_var:
            return None
        val = os.getenv(env_var, "")
        return val if val and val != "your_pipeline_id" else None

    def run_agent(
        self,
        agent_name: str,
        user_input: str,
        async_output: bool = False,
    ) -> dict[str, Any]:
        """
        Route an onlyGen agent call through Airia's AI Gateway.

        Args:
            agent_name : One of: brand_intake, trend_intel, campaign_gen,
                         distribution, feedback_loop
            user_input : The input payload as a string (JSON-encoded if needed)
            async_output: Whether to use async Airia execution

        Returns:
            dict with pipelineOutput and latency_ms

        Raises:
            AiriaNotConfiguredError: if the pipeline GUID is not set in env
            AiriaError: on API failures
        """
        pipeline_id = self.get_pipeline_id(agent_name)
        if not pipeline_id:
            env_var = self.AGENT_ENV_MAP.get(agent_name, f"AIRIA_PIPELINE_{agent_name.upper()}")
            raise AiriaNotConfiguredError(
                f"No Airia pipeline configured for agent '{agent_name}'.\n"
                f"Create an agent in Airia Studio and set:\n"
                f"  {env_var}=<your-pipeline-guid>\n"
                f"in your .env file."
            )
        return self.client.run_pipeline(pipeline_id, user_input, async_output)

    def configured_agents(self) -> dict[str, bool]:
        """Return a map of agent name → whether pipeline GUID is configured."""
        return {name: self.get_pipeline_id(name) is not None for name in self.AGENT_ENV_MAP}
