# API Design

## FastAPI Backend

**Base URL**: `http://localhost:8000/api/v1`

---

## Company Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/companies` | Create company via onboarding (triggers Agent 1) |
| `GET` | `/companies` | List all companies |
| `GET` | `/companies/{id}` | Get company profile |
| `PUT` | `/companies/{id}` | Update company profile |

### `POST /companies` — Request Body
```json
{
  "name": "Acme Fintech",
  "industry": "fintech",
  "tone_of_voice": "professional but approachable",
  "target_audience": "retail investors aged 25-45",
  "campaign_goals": "thought leadership, brand awareness",
  "competitors": ["Robinhood", "Wealthsimple"],
  "visual_style": "clean, modern, data-forward"
}
```

---

## Trend Signal Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/signals` | Get current trend signals |
| `GET` | `/signals/{id}` | Get signal detail with relevance scores |
| `POST` | `/signals/refresh` | Trigger Agent 2 to poll Polymarket now |

### `GET /signals` — Response Example
```json
[
  {
    "id": "sig_abc123",
    "title": "Fed rate cut in March",
    "category": "macro",
    "probability": 0.61,
    "probability_momentum": 0.27,
    "volume": 2100000,
    "volume_velocity": 0.85,
    "relevance_scores": {"company_acme": 0.92}
  }
]
```

---

## Campaign Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/campaigns/generate` | Trigger Agent 3 + 4 pipeline for a company |
| `GET` | `/campaigns` | List campaigns (filterable by company, status) |
| `GET` | `/campaigns/{id}` | Get campaign detail with metrics |
| `POST` | `/campaigns/{id}/approve` | Approve campaign for posting |
| `POST` | `/campaigns/{id}/metrics` | Submit performance metrics (triggers feedback) |

### `POST /campaigns/generate` — Request Body
```json
{
  "company_id": "comp_abc123",
  "signal_id": "sig_abc123",
  "num_concepts": 3
}
```

---

## Feedback & Analytics Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/learning-curve` | Agent improvement over time |
| `GET` | `/analytics/calibration` | Polymarket signal accuracy over time |
| `GET` | `/analytics/patterns` | Cross-company shared patterns |
| `POST` | `/feedback/trigger` | Manually trigger feedback loop cycle |

---

## System Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check with dependency status |
| `GET` | `/agents/status` | Current agent pipeline status |
| `GET` | `/metrics` | Datadog-compatible metrics endpoint |

### `GET /health` — Response Example
```json
{
  "status": "healthy",
  "dependencies": {
    "sqlite": "ok",
    "polymarket_api": "ok",
    "gemini_api": "ok",
    "braintrust": "ok",
    "datadog_agent": "ok"
  },
  "uptime_seconds": 3600
}
```

---

**Prev**: [Data Model](./04-data-model.md) | **Next**: [Frontend Architecture](./06-frontend-architecture.md) | [Full Index](../ARCHITECTURE.md)
