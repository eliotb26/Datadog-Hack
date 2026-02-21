# The Three Self-Improving Loops

These are the core of the hackathon argument. Each loop operates at a different scope and timescale. You need to be able to draw this on a whiteboard in 30 seconds.

---

## Loop 1 — Campaign Performance Feedback (Per-Company)

```
Post Content ──▶ Track Engagement ──▶ Score Campaign ──▶ Update Agent 3 Weights
     ▲                                                          │
     └──────────────────────────────────────────────────────────┘
```

- **Trigger**: Campaign performance data received (simulated or real)
- **Mechanism**: Agent 5 scores campaign outcomes (engagement rate, click-through, sentiment) and updates the content generation agent's prompt template weighting for that specific company
- **Result**: Over time, a fintech client's agent sounds nothing like a gaming client's — learned from outcomes, not just onboarding
- **Sponsor Integration**: Braintrust traces every generation → Loop Agent auto-improves prompts; Airia Battleground A/B tests variations
- **Storage**: `campaign_scores` table in SQLite, prompt weight vectors per company

---

## Loop 2 — Cross-Company Style Learning (Federated)

```
Company A scores ──┐
Company B scores ──┼──▶ Anonymized Aggregate ──▶ Shared Knowledge Layer
Company C scores ──┘                                     │
                                                         ▼
                                              All agents get smarter
```

- **Trigger**: Batch aggregation after N campaigns across the platform
- **Mechanism**: Anonymized style patterns (e.g., "aggressive short-form copy outperforms long-form when Polymarket topic hits 80%+ volume") are extracted and stored in a shared knowledge layer
- **Result**: Emergent collective intelligence — agents teach each other through aggregate signal
- **Sponsor Integration**: Cleric's episodic memory architecture pattern; Lightdash metrics for pattern detection
- **Storage**: `shared_patterns` table; federated style vectors

---

## Loop 3 — Polymarket Signal Calibration

```
Signal Detected ──▶ Content Generated ──▶ Engagement Measured
       ▲                                          │
       └── Update signal-to-engagement weights ◀──┘
```

- **Trigger**: Post-campaign analysis of which Polymarket signals actually predicted engagement
- **Mechanism**: Agent 5 tracks which probability thresholds, categories (politics, crypto, macro), and volume velocity patterns are actually predictive for content virality — versus noise
- **Result**: System stops chasing every spike; learns which trends are worth riding for which company types
- **Sponsor Integration**: Braintrust evaluation scores; Lightdash time-series dashboard showing calibration improvement
- **Storage**: `signal_calibration` table mapping signal features to engagement outcomes

---

## How the Loops Compound

These three loops together are what make SIGNAL genuinely self-improving — not just a tool, but a compounding system:

| Loop | Scope | Timescale | What Improves |
|---|---|---|---|
| Loop 1 | Per-company | After each campaign | Content quality and brand voice |
| Loop 2 | Cross-platform | After N campaigns globally | Collective style intelligence |
| Loop 3 | Signal layer | After each signal-to-campaign cycle | Trend detection accuracy |

---

**Prev**: [Overview](./00-overview.md) | **Next**: [Agent Design](./02-agent-design.md) | [Full Index](../ARCHITECTURE.md)
