# Project Directory Structure

```
Datadog-Hack/
├── ARCHITECTURE.md              # Index document linking to all docs
├── README.md                    # Project overview
├── docker-compose.yml           # Full stack local deployment
├── .env.example                 # Environment variable template
│
├── docs/                        # Architecture documentation (you are here)
│   ├── 00-overview.md
│   ├── 01-self-improving-loops.md
│   ├── 02-agent-design.md
│   ├── 03-sponsor-integrations.md
│   ├── 04-data-model.md
│   ├── 05-api-design.md
│   ├── 06-frontend-architecture.md
│   ├── 07-infrastructure.md
│   ├── 08-observability.md
│   ├── 09-security-safety.md
│   ├── 10-sprint-plan.md
│   ├── 11-tech-stack.md
│   ├── 12-risk-register.md
│   ├── 13-project-structure.md
│   └── 14-demo-script.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                  # FastAPI application entry
│   ├── config.py                # Settings and environment
│   ├── database.py              # SQLite setup and migrations
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── brand_intake.py      # Agent 1 — Brand Intake
│   │   ├── trend_intel.py       # Agent 2 — Trend Intelligence
│   │   ├── campaign_gen.py      # Agent 3 — Campaign Generation
│   │   ├── distribution.py      # Agent 4 — Distribution Routing
│   │   ├── feedback_loop.py     # Agent 5 — Feedback Loop (meta-agent)
│   │   ├── content_strategy.py  # Agent 6 — Content Strategy (format selection)
│   │   └── content_production.py# Agent 7 — Content Production (full content gen)
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── polymarket.py        # Polymarket Gamma API client
│   │   ├── braintrust_eval.py   # Braintrust tracing + eval
│   │   ├── airia_orchestrator.py# Airia workflow management
│   │   ├── modulate_voice.py    # Modulate voice intelligence client
│   │   ├── gemini_media.py      # Gemini image/video generation client
│   │   ├── lightdash_metrics.py # Lightdash data push
│   │   └── datadog_metrics.py   # Custom Datadog metrics
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py           # Company profile model
│   │   ├── signal.py            # Trend signal model
│   │   ├── campaign.py          # Campaign + Distribution models
│   │   ├── content.py           # ContentStrategy + ContentPiece models (Agent 6 & 7)
│   │   └── metrics.py           # Performance metrics model
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── companies.py         # Company CRUD endpoints
│   │   ├── signals.py           # Signal endpoints
│   │   ├── campaigns.py         # Campaign endpoints
│   │   ├── analytics.py         # Analytics endpoints
│   │   └── feedback.py          # Feedback loop endpoints
│   │
│   └── data/
│       └── signal.db            # SQLite database file
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   │
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── pages/
│   │   │   ├── Generate.jsx         # Campaign generation chat UI
│   │   │   ├── Campaigns.jsx        # Campaign list and management
│   │   │   ├── ContentStudio.jsx    # Content strategy + generated content (Agent 6+7)
│   │   │   ├── Trending.jsx         # Polymarket signals feed
│   │   │   └── Settings.jsx         # Brand profile settings
│   │   ├── components/
│   │   │   ├── Layout.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── CampaignCard.jsx
│   │   │   ├── ChannelBadge.jsx
│   │   │   └── ChecklistItem.jsx
│   │   └── lib/
│   │       └── utils.js             # Utility functions + mock data
│   │
│   └── public/
│       └── signal-logo.svg
│
└── scripts/
    ├── seed_demo_data.py        # Pre-seed compelling demo data
    └── simulate_metrics.py      # Generate simulated campaign metrics
```

---

**Prev**: [Risk Register](./12-risk-register.md) | **Next**: [Demo Script](./14-demo-script.md) | [Full Index](../ARCHITECTURE.md)
