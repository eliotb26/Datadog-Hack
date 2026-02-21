# Security, Safety & Brand Voice

## Brand Voice Pipeline (Modulate AI)

```
Voice Brief Recorded
       │
       ▼
┌─────────────────┐
│ Velma-2 STT      │──▶ Transcript + speaker/emotion/accent/PII signals
│ Processing       │
│ (Modulate API)   │
└────────┬────────┘
         │
 Voice Profile Stored
         │
         ▼
 Campaign Generated
         │
         ▼
In-App Alignment Scoring (0.0 - 1.0)
         │
         ▼
 Voice Match Badge + Reviewer Feedback
```

---

## Safety Rules (Airia Agent Constraints)

These rules are enforced centrally at the infrastructure layer via Airia's Agent Constraints policy engine — no per-agent code modifications needed:

- No campaign may reference political figures by name without human approval
- Financial content must include disclaimer language
- Content targeting minors is blocked at the constraint layer
- All generated content must pass Airia policy checks before approval

---

## Data Privacy

- Company data is isolated per tenant (`company_id` foreign keys)
- Cross-company patterns (Loop 2) use only anonymized aggregates — no raw content shared
- SQLite database file is not exposed via API
- All API keys stored as environment variables, never in code

---

## Modulate Voice Metrics (Tracked in Datadog)

| Metric | Source | Purpose |
|---|---|---|
| Voice alignment score | In-app scorer (using Modulate STT outputs) | Mean alignment score per campaign |
| Voice drift rate | In-app scorer (using Modulate STT outputs) | % of campaigns below target voice threshold |
| Reviewer agreement | Human feedback + Modulate scoring | Human/model agreement on voice fit |
| Constraint violations | Airia Agent Constraints | Count of policy-layer rejections |

---

**Prev**: [Observability](./08-observability.md) | **Next**: [Sprint Plan](./10-sprint-plan.md) | [Full Index](../ARCHITECTURE.md)
