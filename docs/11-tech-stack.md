# Tech Stack Summary

## Backend

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | 0.110+ |
| ASGI Server | Uvicorn | 0.27+ |
| Database | SQLite | 3.x (via aiosqlite) |
| LLM SDK | google-genai | latest |
| Agent Framework | google-adk | latest |
| Tracing (LLM) | braintrust | latest |
| Tracing (APM) | ddtrace | latest |
| Metrics | datadog | latest |
| Logging | structlog | latest |
| HTTP Client | httpx | 0.27+ |

## Frontend

| Component | Technology | Version |
|---|---|---|
| Framework | React | 18+ |
| Build Tool | Vite | 5+ |
| Styling | Tailwind CSS | 3+ |
| UI Components | shadcn/ui | latest |
| Charts | Recharts | 2+ |
| HTTP Client | Axios or fetch | — |
| Routing | React Router | 6+ |

## Infrastructure

| Component | Technology |
|---|---|
| Containerization | Docker + Docker Compose |
| Observability | Datadog Agent 7 |
| BI Dashboard | Lightdash (self-hosted) |
| AI Orchestration | Airia Agent Studio |

## External APIs

| API | Purpose | Auth |
|---|---|---|
| Polymarket Gamma API | Prediction market data | Public (no key) |
| Gemini API | LLM inference + image/video generation | API key |
| Braintrust API | Tracing + evaluation | API key |
| Airia API | Agent orchestration | API key |
| Modulate Velma-2 STT APIs | Voice transcription + understanding for brand brief ingestion | API key |

## Python Dependencies (requirements.txt)

```
fastapi
uvicorn[standard]
aiosqlite
google-genai
google-adk
braintrust
ddtrace
datadog
structlog
httpx
python-dotenv
pydantic
```

## Node Dependencies (package.json)

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "react-router-dom": "^6",
    "recharts": "^2",
    "axios": "^1",
    "lucide-react": "latest",
    "class-variance-authority": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest"
  },
  "devDependencies": {
    "vite": "^5",
    "tailwindcss": "^3",
    "@types/react": "^18",
    "typescript": "^5"
  }
}
```

---

**Prev**: [Sprint Plan](./10-sprint-plan.md) | **Next**: [Risk Register](./12-risk-register.md) | [Full Index](../ARCHITECTURE.md)
