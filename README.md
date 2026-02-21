# OnlyGen

**Self-improving content intelligence platform.** OnlyGen (also referred to as SIGNAL in architecture docs) is a living marketing intelligence system that uses prediction market data to generate, distribute, and optimize campaigns — and feeds results back so every campaign gets smarter than the last.

This is not a content scheduler. It’s a compounding system: five agents, three self-improving feedback loops, and real-time signals from [Polymarket](https://polymarket.com) so you create content aligned with what the world is about to care about.

Video: https://youtu.be/J-k0WKh3gfQ

---

## Try it locally

| What | URL |
|------|-----|
| **App (landing + dashboard)** | [http://localhost:3000](http://localhost:3000) |
| **Landing page** | [http://localhost:3000](http://localhost:3000) (root) |
| **Dashboard (create and track campaigns)** | [http://localhost:3000/app](http://localhost:3000/app) |
| **Backend API** | [http://localhost:8000](http://localhost:8000) |
| **API docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) |

---

## How to run

### Prerequisites

- **Node.js** 18+ (for the frontend)
- **Python** 3.11+ (for the backend)
- Optional: API keys in a `.env` (see [Environment variables](#environment-variables))

### 1. Backend (FastAPI)

```bash
# Install dependencies (from repo root)
pip install -r code/backend/requirements.txt

# Run API (from repo root; PYTHONPATH so backend package is found)
PYTHONPATH=code uvicorn backend.main:app --reload --port 8000
```

Backend will be at [http://localhost:8000](http://localhost:8000). Health: [http://localhost:8000](http://localhost:8000) returns `{"service":"SIGNAL","docs":"/docs"}`.

### 2. Frontend (React + Vite)

In a **second terminal**, from the repo root:

```bash
cd code/frontend
npm install
npm run dev
```

Frontend runs at [http://localhost:3000](http://localhost:3000). It proxies `/api` to the backend at `http://localhost:8000`, so use the app at port 3000.

### Quick recap

```bash
# Terminal 1 — backend
PYTHONPATH=code uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd code/frontend && npm run dev
```

Then open **[http://localhost:3000](http://localhost:3000)**.

---

## Environment variables

Optional. Create a `.env` in `code/backend` (or set in the shell) for integrations:

| Variable | Purpose |
|----------|--------|
| `GEMINI_API_KEY` | Google Gemini (LLM) |
| `BRAINTRUST_API_KEY` | Braintrust tracing / eval |
| Others (Airia, Modulate, Flora, Datadog, etc.) | See [docs/07-infrastructure.md](docs/07-infrastructure.md) |

The app runs without these; they’re needed for full agent pipeline and sponsor integrations.

---

## Repo layout

| Path | Description |
|------|-------------|
| **OnlyGen.md** | Product concept, three loops, agents, demo flow |
| **docs/** | Architecture and design (overview, loops, agents, API, infra, etc.) |
| **docs/00-overview.md** | Executive summary and high-level architecture |
| **docs/ARCHITECTURE.md** | Index of all architecture docs |
| **docs/07-infrastructure.md** | Ports, env vars, Docker (when used) |
| **docs/13-project-structure.md** | Directory structure (backend, frontend, scripts) |
| **code/frontend** | React app (landing + dashboard) |
| **code/backend** | FastAPI app (company profile, brand intake, agents) |

---

## Documentation

- **Product vision and flows:** [OnlyGen.md](OnlyGen.md)
- **Architecture index:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Overview (SIGNAL):** [docs/00-overview.md](docs/00-overview.md)
- **Self-improving loops:** [docs/01-self-improving-loops.md](docs/01-self-improving-loops.md)
- **Agent design:** [docs/02-agent-design.md](docs/02-agent-design.md)
- **Infrastructure and run:** [docs/07-infrastructure.md](docs/07-infrastructure.md)
- **Project structure:** [docs/13-project-structure.md](docs/13-project-structure.md)

---

## What’s in the product

- **Landing** ([/](http://localhost:3000)): Hero, video, “Create your Campaign” → app
- **App** ([/app](http://localhost:3000/app)): Generate (brand + brief → campaign ideas), Campaigns, Trending
- **Backend**: Company profile, brand intake, and APIs for the agent pipeline (see [docs/05-api-design.md](docs/05-api-design.md))

Built for the **Building Self-Improving AI Agents** hackathon (Feb 2026). Architecture and sponsor integration details are in the **docs** folder and **OnlyGen.md**.
