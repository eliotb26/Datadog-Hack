"""Structured logging configuration for SIGNAL backend.

Sets up structlog with:
  - JSON rendering for production / Datadog log ingestion
  - Pretty console rendering for local development
  - Datadog trace/span ID injection for log-to-trace correlation
  - Standard fields: timestamp, level, service, env, version

Usage
-----
Call ``configure_logging()`` once at application startup:

    from integrations.logging_setup import configure_logging
    configure_logging()

All other modules then just use:

    import structlog
    log = structlog.get_logger(__name__)
    log.info("campaign_generated", company_id="...", latency_ms=42)
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, MutableMapping

import structlog


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure_logging(level: str | None = None) -> None:
    """Configure structlog for structured JSON logging with Datadog correlation.

    Args:
        level: Log level string (``"DEBUG"``, ``"INFO"``, etc.).
               Defaults to the ``LOG_LEVEL`` env var, or ``"INFO"``.
    """
    log_level_str = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    _configure_stdlib_logging(log_level)

    is_local = os.getenv("ENVIRONMENT", "development").lower() in ("development", "local", "test")
    logs_injection = os.getenv("DD_LOGS_INJECTION", "true").lower() not in ("false", "0", "no")

    processors = _build_processors(pretty=is_local, dd_injection=logs_injection)

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    structlog.get_logger(__name__).debug(
        "logging_configured",
        level=log_level_str,
        pretty=is_local,
        dd_injection=logs_injection,
    )


# ---------------------------------------------------------------------------
# Processor chains
# ---------------------------------------------------------------------------


def _build_processors(pretty: bool, dd_injection: bool) -> list:
    shared: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_service_context,
    ]

    if dd_injection:
        shared.append(_inject_datadog_trace_ids)

    shared += [
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if pretty:
        shared.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        shared.append(structlog.processors.JSONRenderer())

    return shared


# ---------------------------------------------------------------------------
# Custom processors
# ---------------------------------------------------------------------------


def _add_service_context(
    logger: Any,
    method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Inject Datadog unified service tagging fields into every log event."""
    event_dict.setdefault("service", os.getenv("DD_SERVICE", "signal-backend"))
    event_dict.setdefault("env", os.getenv("DD_ENV", "development"))
    event_dict.setdefault("version", os.getenv("DD_VERSION", "0.1.0"))
    return event_dict


def _inject_datadog_trace_ids(
    logger: Any,
    method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Inject current ddtrace trace_id and span_id for log-to-trace correlation.

    This is a no-op when ddtrace is not installed or no active span exists.
    """
    try:
        from ddtrace import tracer

        span = tracer.current_span()
        if span:
            event_dict["dd.trace_id"] = str(span.trace_id)
            event_dict["dd.span_id"] = str(span.span_id)
    except Exception:  # noqa: BLE001
        pass
    return event_dict


# ---------------------------------------------------------------------------
# stdlib logging setup
# ---------------------------------------------------------------------------


def _configure_stdlib_logging(level: int) -> None:
    """Route stdlib logging through structlog for consistent formatting."""
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        root.addHandler(handler)

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "google.auth", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
