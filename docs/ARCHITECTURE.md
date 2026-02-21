# SIGNAL — Architecture Index

## Self-Improving Content Intelligence Platform

**Hackathon**: Building Self-Improving AI Agents | **Build Time**: ~24 hours | **Date**: February 2026

---

## Documentation Map

| # | Document | Description |
|---|---|---|
| 00 | [Overview](./docs/00-overview.md) | Executive summary, sponsor coverage, high-level system diagrams |
| 01 | [Self-Improving Loops](./docs/01-self-improving-loops.md) | The three feedback loops that make SIGNAL a compounding system |
| 02 | [Agent Design](./docs/02-agent-design.md) | All 5 agents: purpose, I/O, LLM choice, ADK patterns, prompt strategies |
| 03 | [Sponsor Integrations](./docs/03-sponsor-integrations.md) | Deep-dive into each of the 8 sponsors with code examples |
| 04 | [Data Model](./docs/04-data-model.md) | SQLite schema (8 tables), entity relationships, design decisions |
| 05 | [API Design](./docs/05-api-design.md) | FastAPI endpoints with request/response examples |
| 06 | [Frontend Architecture](./docs/06-frontend-architecture.md) | React + Vite dashboard: pages, components, key demo moments |
| 07 | [Infrastructure](./docs/07-infrastructure.md) | Docker Compose config, environment variables, service port map |
| 08 | [Observability](./docs/08-observability.md) | Datadog APM + logs + custom metrics, Braintrust complementary roles |
| 09 | [Security & Safety](./docs/09-security-safety.md) | Modulate content safety pipeline, Airia constraints, data privacy |
| 10 | [Sprint Plan](./docs/10-sprint-plan.md) | Hour-by-hour 24h breakdown, MVP vs stretch goals, priority order |
| 11 | [Tech Stack](./docs/11-tech-stack.md) | Full dependency list: backend, frontend, infrastructure, external APIs |
| 12 | [Risk Register](./docs/12-risk-register.md) | 8 risks with mitigations and contingency plans |
| 13 | [Project Structure](./docs/13-project-structure.md) | Complete directory tree for backend, frontend, scripts |
| 14 | [Demo Script](./docs/14-demo-script.md) | 7-minute presentation script with minute-by-minute guide |

---

## Quick Links

**Start here**: [Overview](./docs/00-overview.md) — understand what SIGNAL is and how all sponsors fit

**Core concept**: [Self-Improving Loops](./docs/01-self-improving-loops.md) — the heart of the hackathon pitch

**Build guide**: [Sprint Plan](./docs/10-sprint-plan.md) — hour-by-hour plan with prioritization

**Present**: [Demo Script](./docs/14-demo-script.md) — exactly what to show and say in 7 minutes

---

## Sponsor Integration Summary

| Sponsor | Integration Doc Section | Primary Role |
|---|---|---|
| Google DeepMind | [Section 1](./docs/03-sponsor-integrations.md#1-google-deepmind--core-intelligence-layer) | Gemini API + ADK multi-agent framework |
| Braintrust | [Section 2](./docs/03-sponsor-integrations.md#2-braintrust--evaluation--self-improvement-engine) | Tracing, evaluation, Loop Agent |
| Airia | [Section 3](./docs/03-sponsor-integrations.md#3-airia--enterprise-orchestration) | Orchestration, Battleground A/B |
| Cleric | [Section 4](./docs/03-sponsor-integrations.md#4-cleric--memory-architecture--sre-patterns) | Memory architecture patterns |
| Modulate AI | [Section 5](./docs/03-sponsor-integrations.md#5-modulate-ai--content-safety-layer) | ToxMod content safety |
| Lightdash | [Section 6](./docs/03-sponsor-integrations.md#6-lightdash--analytics--bi-dashboard) | BI dashboard, metrics feedback |
| Flora AI | [Section 7](./docs/03-sponsor-integrations.md#7-flora-ai--creative-asset-generation) | Visual asset generation |
| Datadog | [Section 8](./docs/03-sponsor-integrations.md#8-datadog--full-stack-observability) | APM, logs, custom metrics |
