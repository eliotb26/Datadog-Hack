# Security & Safety Layer

## Content Safety Pipeline (Modulate AI)

```
Campaign Generated
       │
       ▼
┌─────────────────┐
│  Text Analysis   │──▶ Toxicity score, category flags
│  (Modulate API)  │
└────────┬────────┘
         │
    Score > Threshold?
    ┌────┴────┐
    │ YES     │ NO
    ▼         ▼
  BLOCK    APPROVE
  + Log    + Safety
  + Alert  + Badge
  + Human  
  Review   
```

---

## Safety Rules (Airia Agent Constraints)

These rules are enforced centrally at the infrastructure layer via Airia's Agent Constraints policy engine — no per-agent code modifications needed:

- No campaign may reference political figures by name without human approval
- Financial content must include disclaimer language
- Content targeting minors is blocked at the constraint layer
- All generated content must score below 0.3 on Modulate toxicity scale

---

## Data Privacy

- Company data is isolated per tenant (`company_id` foreign keys)
- Cross-company patterns (Loop 2) use only anonymized aggregates — no raw content shared
- SQLite database file is not exposed via API
- All API keys stored as environment variables, never in code

---

## Safety Metrics (Tracked in Lightdash + Datadog)

| Metric | Source | Purpose |
|---|---|---|
| Block rate | Modulate ToxMod | % of campaigns blocked for safety |
| False positive rate | Modulate Appeals API | % of blocks overturned by humans |
| Toxicity distribution | Modulate ToxMod | Histogram of safety scores across campaigns |
| Constraint violations | Airia Agent Constraints | Count of policy-layer rejections |

---

**Prev**: [Observability](./08-observability.md) | **Next**: [Sprint Plan](./10-sprint-plan.md) | [Full Index](../ARCHITECTURE.md)
