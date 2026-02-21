# Agent Design

All agents are built on **Google DeepMind ADK** with **Gemini API** as the reasoning backbone, orchestrated through **Airia Agent Studio** workflows, and traced/evaluated via **Braintrust**.

---

## Agent 1 — Brand Intake Agent

| Property | Value |
|---|---|
| **Purpose** | Onboard a company and build a structured brand profile |
| **Input** | Company name, industry, tone, audience, goals, competitors, content history |
| **Output** | Structured `CompanyProfile` JSON stored in SQLite |
| **LLM** | Gemini 2.5 Flash (fast, cost-efficient for structured extraction) |
| **ADK Pattern** | Single agent with tool calls for profile validation |
| **Airia Integration** | First node in the Airia orchestration workflow |

**Prompt Strategy**: Conversational onboarding that extracts structured data. Uses Gemini's function calling to populate the `CompanyProfile` schema step-by-step.

---

## Agent 2 — Trend Intelligence Agent

| Property | Value |
|---|---|
| **Purpose** | Continuously poll Polymarket and surface actionable trend signals |
| **Input** | Company profile + Polymarket Gamma API market data |
| **Output** | Top 3-5 `TrendSignal` objects per cycle with relevance scores |
| **LLM** | Gemini 2.5 Pro (reasoning-heavy: probability analysis, relevance matching) |
| **ADK Pattern** | Agent with external tool (Polymarket API) + reasoning chain |
| **Key Metrics** | Volume velocity (rate of change), probability momentum, category relevance |

**Signal Filtering Logic**:
1. Poll Polymarket for markets with volume velocity > threshold
2. Filter by probability momentum (not just raw probability)
3. Score relevance to company profile using LLM reasoning
4. Rank and surface top signals with confidence scores

**API Endpoint**: `https://gamma-api.polymarket.com/` — markets, events, price history

---

## Agent 3 — Campaign Generation Agent

| Property | Value |
|---|---|
| **Purpose** | Generate 3-5 campaign concepts from brand profile + trend signals |
| **Input** | `CompanyProfile` + `TrendSignal[]` + historical performance weights |
| **Output** | `CampaignConcept[]` with headline, body, visual direction, confidence, channel rec |
| **LLM** | Gemini 2.5 Pro (creative generation with brand voice adherence) |
| **ADK Pattern** | Agent with brand profile in system prompt; prompt weights updated by Loop 1 |
| **Flora AI Integration** | Generates visual asset suggestions → Flora API creates images |

**Prompt Template** (dynamically weighted):
```
System: You are a campaign strategist for {company.name}.
Brand voice: {company.tone} (weight: {tone_weight})
Target audience: {company.audience}
Style preferences learned from past campaigns: {learned_preferences}

Generate {n} campaign concepts for this trend signal:
{trend_signal}

For each concept provide:
- Headline
- Body copy (50-150 words)
- Visual direction notes
- Confidence score (0-1)
- Recommended channel with reasoning
```

---

## Agent 4 — Distribution Routing Agent

| Property | Value |
|---|---|
| **Purpose** | Score campaigns for channel fit and provide posting recommendations |
| **Input** | `CampaignConcept[]` + channel performance history |
| **Output** | `DistributionPlan` with channel, timing, format adaptation, reasoning |
| **LLM** | Gemini 2.5 Flash (classification task, lower complexity) |
| **ADK Pattern** | Agent with channel knowledge base in context |

**Channel Scoring Matrix**:

| Factor | Twitter/X | LinkedIn | Instagram | Newsletter |
|---|---|---|---|---|
| Post Length | Short (<280) | Medium (500-1500) | Caption (150) | Long (1000+) |
| Visual Weight | Low-Med | Low | High | Medium |
| Audience Match | Broad/Tech | Professional | Consumer | Engaged |
| Best Timing | 9-11 AM, 7-9 PM | Tue-Thu 8-10 AM | Mon-Fri 12-2 PM | Tue/Thu AM |

---

## Agent 5 — Feedback Loop Agent (Meta-Agent)

| Property | Value |
|---|---|
| **Purpose** | Close all three self-improving loops |
| **Input** | Campaign performance data, agent traces, signal history |
| **Output** | Updated weights, patterns, calibration scores |
| **LLM** | Gemini 2.5 Pro (complex multi-step reasoning and evaluation) |
| **ADK Pattern** | Hierarchical orchestrator with 3 sub-agents (one per loop) |
| **Braintrust Integration** | Evaluates all agent outputs; triggers Loop Agent for prompt improvement |

**Sub-Agents**:
- **Loop 1 Sub-Agent**: Analyzes campaign performance → updates Agent 3 prompt weights
- **Loop 2 Sub-Agent**: Aggregates cross-company patterns → updates shared knowledge layer
- **Loop 3 Sub-Agent**: Correlates Polymarket signals with engagement → recalibrates signal weights

---

## ADK Agent Hierarchy

```
                    ┌──────────────────────┐
                    │  Airia Orchestrator   │
                    │  (Workflow Engine)    │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌────────────┐   ┌─────────────┐   ┌──────────┐
     │  Ingestion  │   │  Generation  │   │ Feedback │
     │  Pipeline   │   │  Pipeline    │   │ Pipeline │
     └──────┬─────┘   └──────┬──────┘   └────┬─────┘
            │                │                │
       ┌────┴────┐      ┌───┴───┐       ┌────┴────┐
       ▼         ▼      ▼       ▼       ▼    ▼    ▼
    Agent 1  Agent 2  Agent 3 Agent 4  L1   L2   L3
    Brand    Trend    Campaign Distrib  Sub  Sub  Sub
    Intake   Intel    Gen      Route    Agt  Agt  Agt
```

---

**Prev**: [Self-Improving Loops](./01-self-improving-loops.md) | **Next**: [Sponsor Integrations](./03-sponsor-integrations.md) | [Full Index](../ARCHITECTURE.md)
