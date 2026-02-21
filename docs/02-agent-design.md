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
| **Gemini Media Integration** | Generates image/video asset suggestions → Gemini API creates assets |

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

## Agent 6 — Content Strategy Agent

| Property | Value |
|---|---|
| **Purpose** | Decide what type(s) of content should be generated for a campaign concept |
| **Input** | `CampaignConcept` + `CompanyProfile` context (audience, goals, channel) |
| **Output** | 1-3 `ContentStrategy` objects ranked by expected performance |
| **LLM** | Gemini 2.0 Flash (classification + reasoning task) |
| **ADK Pattern** | Single agent with two tools: `score_content_format`, `format_strategy_output` |

**Content Types Supported**:
- Tweet Thread — 3-8 tweets for Twitter/X
- LinkedIn Article — 800-1500 word long-form professional content
- Blog Post — 1000-2500 word SEO-optimized articles
- Video Script — 60-180 second narrated scripts with visual cues
- Infographic — 5-8 data panel visual content
- Newsletter — 500-1000 word email content
- Instagram Carousel — 5-10 slide visual stories

**Decision Factors**:
1. Audience consumption patterns for the format
2. Channel alignment with the recommended distribution channel
3. Campaign message suitability for the format
4. Production complexity vs. expected ROI

---

## Agent 7 — Content Production Agent

| Property | Value |
|---|---|
| **Purpose** | Generate full-length, publish-ready content from a ContentStrategy |
| **Input** | `ContentStrategy` + original `CampaignConcept` headline/body |
| **Output** | `ContentPiece` — complete, formatted content ready for review |
| **LLM** | Gemini 2.0 Flash (long-form creative generation) |
| **ADK Pattern** | Single agent with two tools: `validate_content_piece`, `format_content_output` |

**Format-Specific Output**:
- **Tweet Threads**: JSON array of individual tweet strings (each ≤280 chars)
- **Articles/Posts/Newsletters**: Markdown-formatted long-form text
- **Video Scripts**: `[VISUAL]` + `[NARRATOR]` formatted script
- **Infographics/Carousels**: JSON array of slide/panel objects with headings and copy

**Quality Controls**:
- Self-validation via `validate_content_piece` tool before finalising
- Word count verification against format guidelines
- Placeholder text detection (rejects Lorem Ipsum, bracket variables)
- Brand alignment scoring

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
       ┌────┴────┐    ┌─────┼─────┐     ┌────┴────┐
       ▼         ▼    ▼     ▼     ▼     ▼    ▼    ▼
    Agent 1  Agent 2  Agt3 Agt4  Agt6  L1   L2   L3
    Brand    Trend    Camp Dist  Cont.  Sub  Sub  Sub
    Intake   Intel    Gen  Route Strat  Agt  Agt  Agt
                                  │
                                  ▼
                               Agent 7
                               Content
                               Production
```

---

**Prev**: [Self-Improving Loops](./01-self-improving-loops.md) | **Next**: [Sponsor Integrations](./03-sponsor-integrations.md) | [Full Index](../ARCHITECTURE.md)
