# SIGNAL — Overview

## Self-Improving Content Intelligence Platform

**Hackathon**: Building Self-Improving AI Agents
**Team Build Time**: ~24 hours
**Date**: February 2026

---

## Executive Summary

SIGNAL is a **living marketing intelligence system** that deploys a multi-agent pipeline to:

1. **Ingest** real-time prediction market data from Polymarket as a leading indicator of emerging trends
2. **Generate** tailored marketing campaigns matched to a company's brand identity
3. **Route** content to optimal distribution channels with timing recommendations
4. **Monitor** campaign performance and feed results back into the system
5. **Self-improve** across three concurrent feedback loops — making every campaign smarter than the last

This is not a content scheduler. It is a compounding intelligence system where every agent interaction, every campaign outcome, and every market signal refines the system's future decisions.

## Sponsor Coverage (8 / 8)

| Sponsor | Role in SIGNAL | Layer |
|---|---|---|
| **Google DeepMind** | LLM backbone (Gemini API) + multi-agent framework (ADK) | Core Intelligence |
| **Braintrust** | Evaluation, tracing, Loop Agent for prompt self-improvement | Evaluation & Improvement |
| **Airia** | Enterprise orchestration, A/B testing, AI Gateway routing | Orchestration |
| **Cleric** | Memory-driven self-improvement architecture patterns, SRE monitoring | Resilience & Memory |
| **Modulate AI** | Content safety auditing before publication via ToxMod | Safety |
| **Lightdash** | BI dashboard for campaign analytics and agent learning curves | Analytics & Feedback |
| **Flora AI** | Creative asset generation (images, visual campaign materials) | Content Production |
| **Datadog** | Full-stack observability: APM, logs, custom metrics, dashboards | Observability |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SIGNAL PLATFORM                               │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ FRONTEND │───▶│  FASTAPI     │───▶│  AGENT       │───▶│ EXTERNAL  │ │
│  │ Dashboard │◀──│  BACKEND     │◀──│  PIPELINE    │◀──│ SERVICES  │ │
│  │ (React)  │    │  (Python)    │    │  (ADK+Airia) │    │           │ │
│  └──────────┘    └──────┬───────┘    └──────┬───────┘    └─────┬─────┘ │
│                         │                   │                  │       │
│                    ┌────▼────┐         ┌────▼────┐       ┌────▼────┐  │
│                    │ SQLite  │         │Braintrust│       │Polymarket│  │
│                    │   DB    │         │ Tracing  │       │Gamma API │  │
│                    └─────────┘         └─────────┘       └─────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    OBSERVABILITY LAYER                           │   │
│  │    Datadog APM  │  Datadog Logs  │  Datadog Custom Metrics      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## System Flow

```
                    ┌─────────────────┐
                    │   Company        │
                    │   Onboarding     │
                    │   (Web UI)       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Agent 1:       │
                    │  Brand Intake   │──────────▶ Company Profile (SQLite)
                    │  (DeepMind ADK) │
                    └────────┬────────┘
                             │
                             ▼
┌──────────────┐   ┌─────────────────┐
│  Polymarket  │──▶│  Agent 2:       │
│  Gamma API   │   │  Trend Intel    │──────────▶ Trend Signals
│  (Live Data) │   │  (DeepMind ADK) │
└──────────────┘   └────────┬────────┘
                             │
                     Company Profile + Trend Signals
                             │
                             ▼
                    ┌─────────────────┐
                    │  Agent 3:       │        ┌──────────────┐
                    │  Campaign Gen   │───────▶│  Flora AI    │
                    │  (DeepMind ADK) │◀───────│  (Visuals)   │
                    └────────┬────────┘        └──────────────┘
                             │
                     Campaign Concepts (3-5 per cycle)
                             │
                    ┌────────▼────────┐
                    │  Modulate AI    │
                    │  Safety Audit   │──────── Block / Flag unsafe content
                    │  (ToxMod API)   │
                    └────────┬────────┘
                             │
                     Approved Campaigns
                             │
                             ▼
                    ┌─────────────────┐
                    │  Agent 4:       │
                    │  Distribution   │──────────▶ Channel Recommendations
                    │  Routing        │            (Twitter, LinkedIn, IG)
                    │  (DeepMind ADK) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────────────────────────────┐
                    │  Agent 5: Feedback Loop (Meta-Agent)    │
                    │                                         │
                    │  ┌───────┐  ┌───────┐  ┌───────┐      │
                    │  │Loop 1 │  │Loop 2 │  │Loop 3 │      │
                    │  │Perf.  │  │Cross- │  │Signal │      │
                    │  │Feedbk │  │Company│  │Calib. │      │
                    │  └───┬───┘  └───┬───┘  └───┬───┘      │
                    │      │          │          │            │
                    │      ▼          ▼          ▼            │
                    │  Update     Shared      Polymarket      │
                    │  Prompts    Knowledge   Weight Map      │
                    └─────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐       ┌──────────────┐
                    │  Lightdash      │◀──────│  Braintrust  │
                    │  BI Dashboard   │       │  Eval Loop   │
                    │  (Metrics)      │       │  Agent       │
                    └─────────────────┘       └──────────────┘
```

---

**Next**: [Self-Improving Loops](./01-self-improving-loops.md) | [Full Index](../ARCHITECTURE.md)
