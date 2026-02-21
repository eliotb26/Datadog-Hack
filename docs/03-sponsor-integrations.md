# Sponsor Integration Map

Detailed integration plan for each of the 8 sponsors.

---

## 1. Google DeepMind — Core Intelligence Layer

**Products Used**:
- **Gemini API** (via `google-genai` Python SDK): All LLM calls
- **Agent Development Kit (ADK)** (`pip install google-adk`): Multi-agent orchestration
- **ADK Eval** (`adk eval`): Built-in evaluation for agent quality measurement

**Integration Points**:
```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

trend_agent = Agent(
    name="trend_intelligence",
    model="gemini-2.5-pro",
    instruction="You are a trend analyst monitoring Polymarket...",
    tools=[
        FunctionTool(poll_polymarket),
        FunctionTool(score_relevance),
        FunctionTool(store_signal),
    ],
)
```

**Why DeepMind**: ADK provides native multi-agent hierarchical orchestration with LLM-driven routing — exactly what SIGNAL needs. Gemini 2.5 Pro's 1M token context window allows loading entire company profiles + market histories in a single call.

---

## 2. Braintrust — Evaluation & Self-Improvement Engine

**Products Used**:
- **Braintrust SDK** (`pip install braintrust`): Trace every LLM call and tool invocation
- **AI Proxy**: Route all Gemini calls through Braintrust for automatic logging
- **Loop Agent**: Auto-generate improved prompts from plain English optimization goals
- **Trace-to-Dataset**: Convert production failures into regression tests with one click

**Integration Points**:
```python
import braintrust

@braintrust.traced
def generate_campaign(company_profile, trend_signals):
    ...

braintrust.loop(
    goal="Improve campaign headline click-through rate",
    dataset=production_traces,
    scorer=engagement_scorer,
)
```

**Self-Improvement Workflow**:
1. All agent calls auto-logged as structured traces
2. Campaign performance scores attached to traces
3. Loop Agent analyzes low-performing traces → generates improved prompts
4. New prompts tested in Braintrust Playground
5. Winning prompts deployed via Braintrust Proxy

---

## 3. Airia — Enterprise Orchestration

**Products Used**:
- **Agent Studio**: Visual workflow builder for the 5-agent pipeline
- **AI Gateway**: Intelligent model routing (Flash for simple tasks, Pro for complex)
- **Battleground**: A/B test different prompt strategies per agent
- **Agent Constraints**: Policy engine for brand safety rules

**Integration Points**:
```
Airia Workflow: SIGNAL Pipeline
├── Node 1: Brand Intake Agent (Gemini Flash via AI Gateway)
├── Node 2: Trend Intel Agent (Gemini Pro via AI Gateway)
├── Node 3: Campaign Gen Agent (Gemini Pro via AI Gateway)
│   └── Sub-node: Flora AI visual generation
├── Node 4: Modulate Safety Check (conditional gate)
├── Node 5: Distribution Router (Gemini Flash via AI Gateway)
└── Node 6: Feedback Loop Agent (Gemini Pro via AI Gateway)
    ├── Sub: Loop 1 - Performance
    ├── Sub: Loop 2 - Cross-company
    └── Sub: Loop 3 - Signal calibration
```

**Battleground A/B Testing**:
- Test aggressive vs. conservative tone for Campaign Gen Agent
- Compare channel routing strategies
- Measure which Polymarket signal thresholds yield best campaigns

---

## 4. Cleric — Memory Architecture & SRE Patterns

**Products Used**:
- **Architecture Patterns**: Three-tier memory system adapted for SIGNAL
- **Progressive Trust Model**: Applied to the feedback loop's autonomy level

**Memory Architecture (Inspired by Cleric)**:

| Memory Tier | Cleric's Version | SIGNAL's Adaptation |
|---|---|---|
| Knowledge Graph | Service dependencies | Company profiles, brand relationships, competitor maps |
| Procedural Memory | Runbooks & processes | Campaign templates, channel strategies, prompt patterns |
| Episodic Memory | Incident records | Campaign outcomes, signal-to-engagement correlations |

**Progressive Trust Model for SIGNAL**:
1. **Level 1 (Day 1)**: Generate campaigns for human review only
2. **Level 2 (After 10 campaigns)**: Auto-post to low-risk channels, suggest for high-risk
3. **Level 3 (After 50 campaigns)**: Full autonomous posting with safety checks
4. **Level 4 (Mature)**: Self-modifying prompt strategies with human override

---

## 5. Modulate AI — Content Safety Layer

**Products Used**:
- **ToxMod API**: Pre-publication content safety screening
- **Appeals API**: Feed overturned decisions back to improve moderation accuracy

**Integration Points**:
```python
def safety_audit(campaign: CampaignConcept) -> SafetyResult:
    """Screen campaign content for brand safety before distribution."""
    result = toxmod.analyze(
        content=campaign.body_copy,
        context=campaign.headline,
        sensitivity_level=company.safety_threshold,
    )
    if result.toxicity_score > SAFETY_THRESHOLD:
        return SafetyResult(blocked=True, reason=result.categories)
    return SafetyResult(blocked=False, safety_score=result.score)
```

**Self-Improvement via Appeals API**:
- When a human reviewer overrides a safety block → feedback sent to Modulate
- Modulate's models refine accuracy based on these outcomes
- Reduces false positives over time

---

## 6. Lightdash — Analytics & BI Dashboard

**Products Used**:
- **Lightdash MCP Server**: Bridge AI agents to governed business metrics
- **Python SDK** (`pip install lightdash`): Programmatic metric queries
- **REST API + Webhooks**: Threshold-based alerts for feedback triggers

**Dashboard Panels**:

| Panel | Metrics | Self-Improvement Signal |
|---|---|---|
| Campaign Performance | Engagement rate, CTR, sentiment by campaign | Feeds Loop 1 |
| Agent Learning Curve | Prompt quality score over time per agent | Shows system getting smarter |
| Polymarket Calibration | Signal accuracy (predicted vs. actual engagement) | Feeds Loop 3 |
| Channel Performance | Engagement by channel × content type | Feeds Agent 4 routing |
| Cross-Company Patterns | Anonymized aggregate style trends | Feeds Loop 2 |
| Safety Metrics | Block rate, false positive rate, appeals | Feeds Modulate improvement |

**This is the demo power moment**: Judges can literally see a graph of the system getting smarter over time.

---

## 7. Flora AI — Creative Asset Generation

**Products Used**:
- **Flora API**: Generate visual campaign assets from text descriptions
- **40+ Model Access**: FLUX, Stable Diffusion, GPT-4o vision for style variety

**Integration Points**:
```python
def generate_campaign_visuals(campaign: CampaignConcept) -> VisualAsset:
    """Generate brand-aligned visual assets via Flora AI."""
    prompt = f"""
    Create a {campaign.visual_direction} image for:
    Brand: {company.name} ({company.industry})
    Campaign: {campaign.headline}
    Style: {company.visual_style}
    """
    return flora_client.generate(
        prompt=prompt,
        model="flux-pro",
        aspect_ratio="16:9",
    )
```

---

## 8. Datadog — Full-Stack Observability

**Products Used**:
- **APM** (`ddtrace`): Distributed tracing across all agent calls
- **Logs**: Structured logging from every pipeline stage
- **Custom Metrics**: Agent performance, API latencies, campaign throughput
- **Dashboards**: Real-time system health and performance
- **Monitors & Alerts**: SLA-based alerting for pipeline failures

**Integration Points**:
```python
from ddtrace import tracer, patch_all
from datadog import initialize, statsd

patch_all()

statsd.increment("signal.campaigns.generated", tags=["company:acme"])
statsd.histogram("signal.agent.latency", duration, tags=["agent:trend_intel"])
statsd.gauge("signal.polymarket.signals_active", count)
```

**Datadog Dashboard Panels**:

| Panel | Metric | Purpose |
|---|---|---|
| Pipeline Health | Request rate, error rate, p95 latency | System reliability |
| Agent Performance | Per-agent latency, token usage, success rate | Cost & speed optimization |
| Polymarket Polling | API response time, data freshness, error rate | Data quality monitoring |
| LLM Costs | Tokens consumed per agent per hour | Budget tracking |
| Feedback Loop Velocity | Time from campaign post to feedback integration | Self-improvement speed |

---

**Prev**: [Agent Design](./02-agent-design.md) | **Next**: [Data Model](./04-data-model.md) | [Full Index](../ARCHITECTURE.md)
