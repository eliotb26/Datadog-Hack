"""Datadog APM tracing setup for SIGNAL agents.

Configures ddtrace for distributed tracing of:
  - FastAPI HTTP requests (auto-instrumented)
  - SQLite / aiosqlite queries (auto-instrumented)
  - Agent runs (manual spans via decorators)
  - External API calls (manual spans)

Usage
-----
Call `configure_tracing()` once at application startup (before FastAPI app init):

    from integrations.dd_tracing import configure_tracing
    configure_tracing()

Then decorate agent functions with `@trace_agent`:

    from integrations.dd_tracing import trace_agent

    @trace_agent("trend_intel")
    async def run_trend_agent(...):
        ...

Or create manual spans inside functions:

    from integrations.dd_tracing import create_span

    with create_span("polymarket.fetch", resource="fetch_top_signals") as span:
        span.set_tag("limit", 50)
        ...
"""
from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

import structlog

log = structlog.get_logger(__name__)

_tracing_configured = False
_tracer = None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def configure_tracing() -> bool:
    """Patch ddtrace integrations and configure the global tracer.

    Safe to call multiple times — subsequent calls are no-ops.

    Returns:
        True if ddtrace was successfully configured, False if skipped or failed.
    """
    global _tracing_configured, _tracer

    if _tracing_configured:
        return True

    if not _is_tracing_enabled():
        log.debug("dd_tracing_disabled", reason="DD_TRACE_ENABLED=false or DD_API_KEY not set")
        return False

    try:
        import ddtrace
        from ddtrace import tracer, patch

        # Auto-patch common integrations present in this project
        patch(
            fastapi=True,
            sqlite=True,
            httpx=True,
            logging=True,
        )

        tracer.configure(
            hostname=os.getenv("DD_AGENT_HOST", "localhost"),
            port=int(os.getenv("DD_TRACE_AGENT_PORT", "8126")),
        )

        _tracer = tracer
        _tracing_configured = True
        log.info(
            "dd_tracing_configured",
            agent_host=os.getenv("DD_AGENT_HOST", "localhost"),
            service=os.getenv("DD_SERVICE", "signal-backend"),
            env=os.getenv("DD_ENV", "development"),
        )
        return True

    except ImportError:
        log.warning("dd_tracing_unavailable", reason="ddtrace package not installed")
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("dd_tracing_init_failed", error=str(exc))
        return False


def _is_tracing_enabled() -> bool:
    """Return True when both DD_API_KEY and DD_TRACE_ENABLED=true are set."""
    api_key = os.getenv("DD_API_KEY", "")
    if not api_key or api_key == "your_datadog_api_key_here":
        return False
    trace_enabled = os.getenv("DD_TRACE_ENABLED", "true").lower()
    return trace_enabled not in ("false", "0", "no")


def get_tracer():
    """Return the ddtrace Tracer instance if available, else None."""
    if _tracer is not None:
        return _tracer
    if not _is_tracing_enabled():
        return None
    try:
        from ddtrace import tracer
        return tracer
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Manual span helpers
# ---------------------------------------------------------------------------


@contextmanager
def create_span(
    name: str,
    resource: Optional[str] = None,
    service: Optional[str] = None,
    span_type: Optional[str] = None,
    tags: Optional[dict] = None,
) -> Generator[Any, None, None]:
    """Context manager that creates a ddtrace span, or is a no-op if tracing is off.

    Args:
        name: Span name (e.g. ``"polymarket.fetch"``).
        resource: Resource identifier (e.g. function name, SQL query).
        service: Override service name; defaults to DD_SERVICE env var.
        span_type: Span type tag (e.g. ``"web"``, ``"db"``, ``"http"``).
        tags: Extra key-value tags to attach to the span.

    Yields:
        The active ddtrace Span, or a :class:`_NoopSpan` when tracing is disabled.
    """
    tracer = get_tracer()
    if tracer is None:
        yield _NoopSpan()
        return

    svc = service or os.getenv("DD_SERVICE", "signal-backend")
    with tracer.trace(name, resource=resource, service=svc, span_type=span_type) as span:
        if tags:
            for k, v in tags.items():
                span.set_tag(k, v)
        try:
            yield span
        except Exception as exc:
            span.error = 1
            span.set_tag("error.message", str(exc))
            span.set_tag("error.type", type(exc).__name__)
            raise


# ---------------------------------------------------------------------------
# Agent span decorator
# ---------------------------------------------------------------------------


def trace_agent(agent_name: str):
    """Decorator that wraps an agent function in a ddtrace span.

    Works on both sync and async functions. The span is tagged with:
      - ``agent.name``
      - ``agent.company_id`` (extracted from a ``company`` kwarg / first positional arg if present)

    Usage::

        @trace_agent("trend_intel")
        async def run_trend_agent(company, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if _is_async(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                company_id = _extract_company_id(args, kwargs)
                with create_span(
                    f"signal.agent.{agent_name}",
                    resource=func.__name__,
                    tags={"agent.name": agent_name, "agent.company_id": company_id},
                ) as span:
                    try:
                        result = await func(*args, **kwargs)
                        span.set_tag("agent.success", True)
                        return result
                    except Exception as exc:
                        span.set_tag("agent.success", False)
                        span.set_tag("error.message", str(exc))
                        raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                company_id = _extract_company_id(args, kwargs)
                with create_span(
                    f"signal.agent.{agent_name}",
                    resource=func.__name__,
                    tags={"agent.name": agent_name, "agent.company_id": company_id},
                ) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_tag("agent.success", True)
                        return result
                    except Exception as exc:
                        span.set_tag("agent.success", False)
                        span.set_tag("error.message", str(exc))
                        raise

            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_async(func: Callable) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(func)


def _extract_company_id(args: tuple, kwargs: dict) -> str:
    """Best-effort extraction of company_id from agent function arguments."""
    # Check kwargs first
    if "company_id" in kwargs:
        return str(kwargs["company_id"])
    company = kwargs.get("company")
    if company is None and args:
        company = args[0]
    if company is not None and hasattr(company, "id"):
        return str(company.id)
    return "unknown"


def get_current_trace_ids() -> dict:
    """Return current trace_id and span_id for log correlation.

    Returns an empty dict when tracing is not active.
    """
    tracer = get_tracer()
    if tracer is None:
        return {}
    try:
        span = tracer.current_span()
        if span is None:
            return {}
        return {
            "dd.trace_id": str(span.trace_id),
            "dd.span_id": str(span.span_id),
            "dd.service": os.getenv("DD_SERVICE", "signal-backend"),
            "dd.env": os.getenv("DD_ENV", "development"),
        }
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# No-op span (used when tracing is disabled)
# ---------------------------------------------------------------------------


class _NoopSpan:
    """Minimal span interface that does nothing — used when ddtrace is not active."""

    error: int = 0

    def set_tag(self, key: str, value: Any) -> None:
        pass

    def finish(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
