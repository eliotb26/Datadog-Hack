# Observability Stack

## Datadog Integration Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   FastAPI     │────▶│   ddtrace    │────▶│   Datadog    │
│   Backend     │     │   (APM)      │     │   Agent      │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
┌──────────────┐     ┌──────────────┐            │
│  Agent Calls  │────▶│  structlog   │────────────┤
│  (ADK)        │     │  (Logs)      │            │
└──────────────┘     └──────────────┘            │
                                                  │
┌──────────────┐     ┌──────────────┐            │
│  Custom       │────▶│  DogStatsD   │────────────┘
│  Metrics      │     │  (Gauges)    │
└──────────────┘     └──────────────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │   Datadog     │
                                          │   Cloud       │
                                          │   Dashboard   │
                                          └──────────────┘
```

---

## Key Datadog Monitors

| Monitor | Condition | Alert |
|---|---|---|
| Pipeline Latency | p95 > 30s for campaign generation | Warning |
| Agent Error Rate | > 5% errors in any agent over 5 min | Critical |
| Polymarket API Health | > 3 consecutive failures | Critical |
| LLM Token Burn | > 1M tokens/hour | Warning (cost) |
| Feedback Loop Stall | No feedback cycle completed in 1 hour | Warning |

---

## Braintrust + Datadog Complementary Roles

These two observability tools serve different purposes and do not overlap:

| Concern | Braintrust | Datadog |
|---|---|---|
| LLM output quality | Evaluation scores, prompt improvement | — |
| System performance | — | APM traces, latency, error rates |
| Cost tracking | Token usage per trace | Token metrics aggregated |
| Self-improvement | Loop Agent, trace-to-dataset | Metric trends over time |
| Alerting | CI/CD eval gates | Monitor-based alerts |

---

## Custom Metrics Emitted

```python
from datadog import statsd

# Campaign pipeline metrics
statsd.increment("signal.campaigns.generated", tags=["company:{id}"])
statsd.increment("signal.campaigns.approved")
statsd.increment("signal.campaigns.blocked_safety")

# Agent performance metrics
statsd.histogram("signal.agent.latency_ms", duration, tags=["agent:{name}"])
statsd.histogram("signal.agent.tokens_used", tokens, tags=["agent:{name}"])
statsd.increment("signal.agent.errors", tags=["agent:{name}", "error:{type}"])

# Polymarket polling metrics
statsd.gauge("signal.polymarket.signals_active", count)
statsd.histogram("signal.polymarket.poll_latency_ms", duration)
statsd.increment("signal.polymarket.api_errors")

# Feedback loop metrics
statsd.histogram("signal.feedback.loop_duration_ms", duration, tags=["loop:{n}"])
statsd.gauge("signal.feedback.prompt_quality_score", score, tags=["agent:{name}"])
statsd.increment("signal.feedback.weight_updates")
```

---

## Structured Logging Format

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "campaign_generated",
    company_id=company.id,
    signal_id=signal.id,
    campaign_id=campaign.id,
    confidence=campaign.confidence_score,
    channel=campaign.channel_recommendation,
    safety_score=campaign.safety_score,
    latency_ms=elapsed,
)
```

All logs are JSON-formatted and forwarded to Datadog via the Datadog Agent's log collection.

---

**Prev**: [Infrastructure](./07-infrastructure.md) | **Next**: [Security & Safety](./09-security-safety.md) | [Full Index](../ARCHITECTURE.md)
