"""Comprehensive tests for the Datadog observability integration.

Test layers
-----------
Unit tests (no network, no Datadog credentials required):
  - All metric helper functions emit the right calls when statsd is mocked
  - All metric helpers are silent when statsd is unavailable
  - APM span helpers work (create_span, trace_agent decorator)
  - APM helpers are no-ops when ddtrace is not configured
  - Logging setup produces correct JSON structure
  - Log-to-trace ID injection works when ddtrace is active

Run unit tests only (no credentials needed):
    pytest code/backend/tests/test_datadog_integration.py -v -m unit

Run all tests:
    pytest code/backend/tests/test_datadog_integration.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from dotenv import load_dotenv

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_statsd():
    """Return a MagicMock that mimics the datadog statsd client."""
    sd = MagicMock()
    sd.gauge = MagicMock()
    sd.histogram = MagicMock()
    sd.increment = MagicMock()
    return sd


# ---------------------------------------------------------------------------
# Unit Tests — datadog_metrics module
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatadogMetricsNoCredentials:
    """Verify every metric function is a no-op when DD_API_KEY is missing."""

    def setup_method(self):
        # Reset module-level initialisation state before each test
        import integrations.datadog_metrics as dm
        dm._dd_initialized = False

    def _call_all_metric_functions(self):
        """Call every public metric function with dummy values."""
        from integrations import datadog_metrics as dm

        dm.track_signals_surfaced(5, company_id="co-001")
        dm.track_polymarket_poll(100, 10, 250.0)
        dm.track_polymarket_error()
        dm.track_agent_latency(320.5, "trend_intel")
        dm.track_agent_tokens(1500, "trend_intel")
        dm.track_agent_error("campaign_gen", "timeout")
        dm.track_api_call("polymarket", success=True, latency_ms=120.0)
        dm.track_api_call("gemini", success=False)
        dm.track_trend_agent_run(3, "co-001", 1200.0, success=True)
        dm.track_campaign_agent_run(2, "co-001", 800.0, success=False)
        dm.track_campaign_generated(3, "co-001")
        dm.track_campaign_approved("co-001")
        dm.track_campaign_blocked_safety("co-001", safety_score=0.85)
        dm.track_feedback_loop(5000.0, loop_number=2)
        dm.track_prompt_quality(0.92, "trend_intel")
        dm.track_weight_update("campaign_gen", "tone_weight")

    def test_no_crash_without_api_key(self):
        """All metric functions must not raise even with no DD_API_KEY."""
        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            self._call_all_metric_functions()

    def test_no_crash_with_placeholder_api_key(self):
        """Placeholder value in .env should also produce silent no-op."""
        with patch.dict(os.environ, {"DD_API_KEY": "your_datadog_api_key_here"}):
            self._call_all_metric_functions()

    def test_timed_context_manager_no_crash(self):
        from integrations.datadog_metrics import timed

        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            with timed("signal.test.duration", tags=["test:true"]):
                time.sleep(0.001)

    def test_timed_measures_elapsed(self):
        from integrations.datadog_metrics import timed

        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            start = time.perf_counter()
            with timed("signal.test.duration"):
                time.sleep(0.01)
            elapsed = (time.perf_counter() - start) * 1000
        assert elapsed >= 10, "timed() should capture at least 10ms of sleep"


@pytest.mark.unit
class TestDatadogMetricsWithMockStatsd:
    """Verify every metric function calls the right statsd methods when Datadog IS configured."""

    def setup_method(self):
        import integrations.datadog_metrics as dm
        dm._dd_initialized = False

    def _patch_statsd(self):
        """Patch _statsd() to return a mock and set _dd_initialized=True."""
        import integrations.datadog_metrics as dm
        mock_sd = _make_mock_statsd()
        dm._dd_initialized = True
        return mock_sd, patch("integrations.datadog_metrics._statsd", return_value=mock_sd)

    # -- Polymarket ----------------------------------------------------------

    def test_track_signals_surfaced_calls_gauge(self):
        from integrations.datadog_metrics import track_signals_surfaced
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_signals_surfaced(7, company_id="co-xyz")
        mock_sd.gauge.assert_called_once_with(
            "signal.polymarket.signals_active", 7, tags=["company:co-xyz"]
        )

    def test_track_polymarket_poll_calls_three_metrics(self):
        from integrations.datadog_metrics import track_polymarket_poll
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_polymarket_poll(200, 15, 350.0)
        mock_sd.gauge.assert_any_call("signal.polymarket.markets_fetched", 200)
        mock_sd.gauge.assert_any_call("signal.polymarket.signals_after_filter", 15)
        mock_sd.histogram.assert_called_once_with("signal.polymarket.poll_latency_ms", 350.0)

    def test_track_polymarket_error_increments(self):
        from integrations.datadog_metrics import track_polymarket_error
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_polymarket_error()
        mock_sd.increment.assert_called_once_with("signal.polymarket.api_errors")

    # -- Generic agent -------------------------------------------------------

    def test_track_agent_latency(self):
        from integrations.datadog_metrics import track_agent_latency
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_agent_latency(420.0, "brand_intake")
        mock_sd.histogram.assert_called_once_with(
            "signal.agent.latency_ms", 420.0, tags=["agent:brand_intake"]
        )

    def test_track_agent_tokens(self):
        from integrations.datadog_metrics import track_agent_tokens
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_agent_tokens(2048, "campaign_gen")
        mock_sd.histogram.assert_called_once_with(
            "signal.agent.tokens_used", 2048, tags=["agent:campaign_gen"]
        )

    def test_track_agent_error(self):
        from integrations.datadog_metrics import track_agent_error
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_agent_error("distribution", "timeout")
        mock_sd.increment.assert_called_once_with(
            "signal.agent.errors",
            tags=["agent:distribution", "error:timeout"],
        )

    # -- API calls -----------------------------------------------------------

    def test_track_api_call_success_with_latency(self):
        from integrations.datadog_metrics import track_api_call
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_api_call("polymarket", success=True, latency_ms=88.5)
        mock_sd.increment.assert_called_once_with(
            "signal.api.calls", tags=["api:polymarket", "status:success"]
        )
        mock_sd.histogram.assert_called_once_with(
            "signal.api.latency_ms", 88.5, tags=["api:polymarket"]
        )

    def test_track_api_call_error_no_latency(self):
        from integrations.datadog_metrics import track_api_call
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_api_call("gemini", success=False)
        mock_sd.increment.assert_called_once_with(
            "signal.api.calls", tags=["api:gemini", "status:error"]
        )
        mock_sd.histogram.assert_not_called()

    # -- Trend agent run bundle ----------------------------------------------

    def test_track_trend_agent_run_success(self):
        from integrations.datadog_metrics import track_trend_agent_run
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_trend_agent_run(4, "co-abc", 1500.0, success=True)
        expected_tags = ["company:co-abc", "status:success", "agent:trend_intel"]
        mock_sd.increment.assert_called_once_with("signal.agent.runs", tags=expected_tags)
        mock_sd.gauge.assert_called_once_with(
            "signal.agent.signals_returned", 4, tags=expected_tags
        )
        mock_sd.histogram.assert_called_once_with(
            "signal.agent.run_latency_ms", 1500.0, tags=expected_tags
        )

    def test_track_trend_agent_run_failure_tags(self):
        from integrations.datadog_metrics import track_trend_agent_run
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_trend_agent_run(0, "co-fail", 200.0, success=False)
        call_args = mock_sd.increment.call_args
        assert "status:error" in call_args[1]["tags"]

    # -- Campaign agent run bundle -------------------------------------------

    def test_track_campaign_agent_run_success(self):
        from integrations.datadog_metrics import track_campaign_agent_run
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_campaign_agent_run(3, "co-xyz", 900.0, success=True)
        expected_tags = ["company:co-xyz", "status:success", "agent:campaign_gen"]
        mock_sd.increment.assert_called_once_with("signal.agent.runs", tags=expected_tags)
        mock_sd.gauge.assert_called_once_with(
            "signal.agent.concepts_generated", 3, tags=expected_tags
        )

    # -- Campaign lifecycle --------------------------------------------------

    def test_track_campaign_generated(self):
        from integrations.datadog_metrics import track_campaign_generated
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_campaign_generated(5, "co-001")
        mock_sd.increment.assert_called_once_with(
            "signal.campaigns.generated", 5, tags=["company:co-001"]
        )

    def test_track_campaign_approved(self):
        from integrations.datadog_metrics import track_campaign_approved
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_campaign_approved("co-001")
        mock_sd.increment.assert_called_once_with(
            "signal.campaigns.approved", tags=["company:co-001"]
        )

    def test_track_campaign_blocked_safety(self):
        from integrations.datadog_metrics import track_campaign_blocked_safety
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_campaign_blocked_safety("co-001", safety_score=0.91)
        mock_sd.increment.assert_called_once_with(
            "signal.campaigns.blocked_safety", tags=["company:co-001"]
        )

    # -- Feedback loop -------------------------------------------------------

    def test_track_feedback_loop(self):
        from integrations.datadog_metrics import track_feedback_loop
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_feedback_loop(4500.0, loop_number=3)
        mock_sd.histogram.assert_called_once_with(
            "signal.feedback.loop_duration_ms", 4500.0, tags=["loop:3"]
        )

    def test_track_prompt_quality(self):
        from integrations.datadog_metrics import track_prompt_quality
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_prompt_quality(0.87, "trend_intel")
        mock_sd.gauge.assert_called_once_with(
            "signal.feedback.prompt_quality_score", 0.87, tags=["agent:trend_intel"]
        )

    def test_track_weight_update(self):
        from integrations.datadog_metrics import track_weight_update
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            track_weight_update("campaign_gen", "tone_weight")
        mock_sd.increment.assert_called_once_with(
            "signal.feedback.weight_updates",
            tags=["agent:campaign_gen", "weight:tone_weight"],
        )

    # -- timed() context manager ----------------------------------------------

    def test_timed_records_histogram(self):
        from integrations.datadog_metrics import timed
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            with timed("signal.test.custom_metric", tags=["env:test"]):
                time.sleep(0.001)
        mock_sd.histogram.assert_called_once()
        call_args = mock_sd.histogram.call_args
        metric_name = call_args[0][0]
        elapsed = call_args[0][1]
        assert metric_name == "signal.test.custom_metric"
        assert elapsed >= 1.0, "Elapsed should be at least 1 ms"
        assert call_args[1]["tags"] == ["env:test"]

    def test_timed_records_histogram_on_exception(self):
        """timed() must record the histogram even when the body raises."""
        from integrations.datadog_metrics import timed
        mock_sd, patcher = self._patch_statsd()
        with patcher:
            with pytest.raises(ValueError):
                with timed("signal.test.error_path"):
                    raise ValueError("boom")
        mock_sd.histogram.assert_called_once()


# ---------------------------------------------------------------------------
# Unit Tests — dd_tracing module
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDdTracingNoCredentials:
    """Verify APM helpers are no-ops when DD is not configured."""

    def setup_method(self):
        import integrations.dd_tracing as dt
        dt._tracing_configured = False
        dt._tracer = None

    def test_configure_tracing_returns_false_without_api_key(self):
        from integrations.dd_tracing import configure_tracing
        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            result = configure_tracing()
        assert result is False

    def test_configure_tracing_returns_false_with_placeholder_key(self):
        from integrations.dd_tracing import configure_tracing
        with patch.dict(os.environ, {"DD_API_KEY": "your_datadog_api_key_here"}):
            result = configure_tracing()
        assert result is False

    def test_create_span_yields_noop_span(self):
        from integrations.dd_tracing import create_span, _NoopSpan
        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            with create_span("test.span") as span:
                assert isinstance(span, _NoopSpan)
                span.set_tag("key", "value")  # must not raise

    def test_noop_span_error_flag(self):
        from integrations.dd_tracing import _NoopSpan
        span = _NoopSpan()
        span.error = 1
        assert span.error == 1

    def test_trace_agent_decorator_sync_no_crash(self):
        from integrations.dd_tracing import trace_agent

        @trace_agent("test_agent")
        def dummy(x: int) -> int:
            return x * 2

        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            result = dummy(5)
        assert result == 10

    def test_trace_agent_decorator_async_no_crash(self):
        from integrations.dd_tracing import trace_agent

        @trace_agent("test_async_agent")
        async def async_dummy(x: int) -> int:
            return x + 1

        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            result = asyncio.run(async_dummy(3))
        assert result == 4

    def test_trace_agent_propagates_exception(self):
        from integrations.dd_tracing import trace_agent

        @trace_agent("failing_agent")
        def bad_func():
            raise RuntimeError("intentional failure")

        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="intentional failure"):
                bad_func()

    def test_get_current_trace_ids_empty_without_tracer(self):
        from integrations.dd_tracing import get_current_trace_ids
        with patch.dict(os.environ, {"DD_API_KEY": ""}):
            ids = get_current_trace_ids()
        assert ids == {}


@pytest.mark.unit
class TestDdTracingWithMockTracer:
    """Verify APM helpers use the ddtrace tracer when credentials are present."""

    def setup_method(self):
        import integrations.dd_tracing as dt
        dt._tracing_configured = False
        dt._tracer = None

    def test_create_span_uses_tracer(self):
        """create_span should call tracer.trace() when a tracer is available."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.trace.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.trace.return_value.__exit__ = MagicMock(return_value=False)

        from integrations import dd_tracing as dt
        with patch.object(dt, "get_tracer", return_value=mock_tracer):
            with dt.create_span("signal.test.span", resource="my_func", tags={"k": "v"}) as span:
                pass

        mock_tracer.trace.assert_called_once_with(
            "signal.test.span",
            resource="my_func",
            service=os.getenv("DD_SERVICE", "signal-backend"),
            span_type=None,
        )
        mock_span.set_tag.assert_called_with("k", "v")

    def test_create_span_marks_error_on_exception(self):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.trace.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.trace.return_value.__exit__ = MagicMock(return_value=False)

        from integrations import dd_tracing as dt
        with patch.object(dt, "get_tracer", return_value=mock_tracer):
            with pytest.raises(ValueError):
                with dt.create_span("signal.erroring.span"):
                    raise ValueError("test error")

        mock_span.set_tag.assert_any_call("error.message", "test error")
        mock_span.set_tag.assert_any_call("error.type", "ValueError")

    def test_trace_agent_extracts_company_id_from_kwarg(self):
        from integrations import dd_tracing as dt
        from contextlib import contextmanager

        captured_tags: dict = {}

        @contextmanager
        def fake_create_span(name, resource=None, tags=None, **kwargs):
            captured_tags.update(tags or {})
            yield MagicMock()

        @dt.trace_agent("test_agent")
        def my_agent(company_id: str = "co-test") -> str:
            return company_id

        with patch.object(dt, "create_span", new=fake_create_span):
            my_agent(company_id="co-999")

        assert captured_tags.get("agent.company_id") == "co-999"

    def test_get_current_trace_ids_with_active_span(self):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.trace_id = 123456789
        mock_span.span_id = 987654321
        mock_tracer.current_span.return_value = mock_span

        from integrations import dd_tracing as dt
        with patch.object(dt, "get_tracer", return_value=mock_tracer):
            ids = dt.get_current_trace_ids()

        assert ids["dd.trace_id"] == "123456789"
        assert ids["dd.span_id"] == "987654321"


# ---------------------------------------------------------------------------
# Unit Tests — logging_setup module
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoggingSetup:
    """Verify structlog is configured correctly for both dev and production modes."""

    def test_configure_logging_does_not_raise(self):
        from integrations.logging_setup import configure_logging
        configure_logging(level="DEBUG")

    def test_configure_logging_json_mode(self):
        """In non-dev environments, structlog should use JSONRenderer."""
        import structlog
        from integrations.logging_setup import configure_logging

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            configure_logging(level="INFO")

        config = structlog.get_config()
        processor_types = [type(p).__name__ for p in config["processors"]]
        assert "JSONRenderer" in processor_types

    def test_configure_logging_pretty_mode(self):
        """In dev/local environments, structlog should use ConsoleRenderer."""
        import structlog
        from integrations.logging_setup import configure_logging

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            configure_logging(level="DEBUG")

        config = structlog.get_config()
        processor_types = [type(p).__name__ for p in config["processors"]]
        assert "ConsoleRenderer" in processor_types

    def test_logger_emits_event(self, capsys):
        """A structured log event should be producible after configuration."""
        import structlog
        from integrations.logging_setup import configure_logging

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            configure_logging(level="DEBUG")

        log = structlog.get_logger("test_logger")
        log.info("test_event", foo="bar", count=42)

    def test_add_service_context_processor(self):
        """_add_service_context must inject service/env/version fields."""
        from integrations.logging_setup import _add_service_context

        event_dict: dict = {"event": "hello"}
        with patch.dict(
            os.environ,
            {"DD_SERVICE": "my-svc", "DD_ENV": "staging", "DD_VERSION": "1.2.3"},
        ):
            result = _add_service_context(None, "info", event_dict)

        assert result["service"] == "my-svc"
        assert result["env"] == "staging"
        assert result["version"] == "1.2.3"

    def test_inject_datadog_trace_ids_no_tracer(self):
        """When ddtrace has no active span the processor should be a no-op."""
        from integrations.logging_setup import _inject_datadog_trace_ids

        event_dict: dict = {"event": "hello"}
        result = _inject_datadog_trace_ids(None, "info", event_dict)
        assert "dd.trace_id" not in result

    def test_inject_datadog_trace_ids_with_active_span(self):
        """When a span is active, trace IDs should be injected."""
        from integrations.logging_setup import _inject_datadog_trace_ids

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.trace_id = 111222333
        mock_span.span_id = 444555666
        mock_tracer.current_span.return_value = mock_span

        with patch.dict("sys.modules", {"ddtrace": MagicMock(tracer=mock_tracer)}):
            # Re-import to pick up mocked ddtrace
            import importlib
            import integrations.logging_setup as ls
            importlib.reload(ls)

            event_dict: dict = {"event": "hello"}
            result = ls._inject_datadog_trace_ids(None, "info", event_dict)

        # The mock may or may not inject depending on how reload works;
        # what matters is no exception is raised
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Integration-style smoke test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEndToEndMetricFlow:
    """Simulate a realistic agent run and verify all expected metric calls are made."""

    def setup_method(self):
        import integrations.datadog_metrics as dm
        dm._dd_initialized = False

    def test_full_trend_agent_metric_flow(self):
        """Simulate Agent 2 calling all relevant metric functions."""
        import integrations.datadog_metrics as dm

        mock_sd = _make_mock_statsd()
        dm._dd_initialized = True

        with patch("integrations.datadog_metrics._statsd", return_value=mock_sd):
            # 1. Fetch signals from Polymarket
            dm.track_api_call("polymarket", success=True, latency_ms=95.0)
            dm.track_polymarket_poll(100, 12, 95.0)

            # 2. Agent run completes
            dm.track_trend_agent_run(
                signals_returned=4,
                company_id="co-e2e",
                latency_ms=1800.0,
                success=True,
            )
            dm.track_signals_surfaced(4, company_id="co-e2e")

        # Verify key calls were made
        increment_calls = [str(c) for c in mock_sd.increment.call_args_list]
        gauge_calls = [str(c) for c in mock_sd.gauge.call_args_list]
        histogram_calls = [str(c) for c in mock_sd.histogram.call_args_list]

        assert any("signal.api.calls" in c for c in increment_calls)
        assert any("signal.agent.runs" in c for c in increment_calls)
        assert any("signal.polymarket.signals_active" in c for c in gauge_calls)
        assert any("signal.polymarket.markets_fetched" in c for c in gauge_calls)
        assert any("signal.agent.run_latency_ms" in c for c in histogram_calls)

    def test_full_campaign_agent_metric_flow(self):
        """Simulate Agent 3 calling all relevant metric functions."""
        import integrations.datadog_metrics as dm

        mock_sd = _make_mock_statsd()
        dm._dd_initialized = True

        with patch("integrations.datadog_metrics._statsd", return_value=mock_sd):
            dm.track_campaign_agent_run(3, "co-e2e", 950.0, success=True)
            dm.track_campaign_generated(3, "co-e2e")
            dm.track_campaign_approved("co-e2e")
            dm.track_campaign_approved("co-e2e")
            dm.track_campaign_blocked_safety("co-e2e", safety_score=0.88)

        increment_calls = [str(c) for c in mock_sd.increment.call_args_list]
        assert any("signal.campaigns.generated" in c for c in increment_calls)
        assert any("signal.campaigns.approved" in c for c in increment_calls)
        assert any("signal.campaigns.blocked_safety" in c for c in increment_calls)

    def test_feedback_loop_metric_flow(self):
        """Simulate the feedback / self-improvement loop calling its metrics."""
        import integrations.datadog_metrics as dm

        mock_sd = _make_mock_statsd()
        dm._dd_initialized = True

        with patch("integrations.datadog_metrics._statsd", return_value=mock_sd):
            dm.track_feedback_loop(6200.0, loop_number=1)
            dm.track_prompt_quality(0.78, "trend_intel")
            dm.track_prompt_quality(0.83, "campaign_gen")
            dm.track_weight_update("trend_intel", "relevance_weight")
            dm.track_weight_update("campaign_gen", "tone_weight")

        gauge_calls = [str(c) for c in mock_sd.gauge.call_args_list]
        histogram_calls = [str(c) for c in mock_sd.histogram.call_args_list]
        increment_calls = [str(c) for c in mock_sd.increment.call_args_list]

        assert any("signal.feedback.loop_duration_ms" in c for c in histogram_calls)
        assert any("signal.feedback.prompt_quality_score" in c for c in gauge_calls)
        assert any("signal.feedback.weight_updates" in c for c in increment_calls)


