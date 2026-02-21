# Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Polymarket API rate limiting | Medium | High | Cache responses, poll every 5 min not every second |
| Gemini API latency spikes | Medium | Medium | Use Flash for simple tasks, Pro only where needed |
| Flora AI API undocumented | High | Medium | Fallback to placeholder images if API unavailable |
| Modulate API integration complexity | Medium | Low | Fallback to text-only voice profile input if audio analysis API is unstable |
| 24h not enough for all 8 sponsors | High | High | Prioritize DeepMind + Braintrust + Datadog core; others can be lighter |
| SQLite concurrent write issues | Low | Low | Single-writer pattern; WAL mode enabled |
| Lightdash self-hosted setup time | Medium | Medium | Use Lightdash Cloud free trial as fallback |
| Demo data not compelling | Medium | High | Pre-seed with real Polymarket data from morning of demo |

---

## Contingency Plans

### If Polymarket API is down
- Pre-cache 24 hours of real market data in `demo_data.json`
- Serve cached data from a mock endpoint
- Annotate in demo: "We're showing cached data from this morning"

### If a sponsor API is unreachable
- Each integration module has a `MOCK_MODE` flag
- When `True`, returns realistic simulated responses
- Allows full demo flow without live API connectivity

### If time runs out
- Follow the priority order in [Sprint Plan](./10-sprint-plan.md#priority-order-if-running-out-of-time)
- Core flow (Agents 1-3 + one feedback loop + Datadog tracing) is the minimum viable demo
- Every additional sponsor integration is additive, not blocking

---

**Prev**: [Tech Stack](./11-tech-stack.md) | **Next**: [Project Structure](./13-project-structure.md) | [Full Index](../ARCHITECTURE.md)
