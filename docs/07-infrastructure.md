# Infrastructure & Deployment

## Docker Compose (Local Demo)

```yaml
version: "3.9"

services:
  # Python FastAPI backend
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - BRAINTRUST_API_KEY=${BRAINTRUST_API_KEY}
      - AIRIA_API_KEY=${AIRIA_API_KEY}
      - MODULATE_API_KEY=${MODULATE_API_KEY}
      - FLORA_API_KEY=${FLORA_API_KEY}
      - DD_SERVICE=signal-backend
      - DD_ENV=hackathon
      - DD_AGENT_HOST=datadog-agent
    volumes:
      - ./data:/app/data  # SQLite database
    depends_on:
      - datadog-agent

  # React frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  # Datadog Agent for observability
  datadog-agent:
    image: gcr.io/datadoghq/agent:7
    environment:
      - DD_API_KEY=${DD_API_KEY}
      - DD_SITE=datadoghq.com
      - DD_APM_ENABLED=true
      - DD_LOGS_ENABLED=true
      - DD_PROCESS_AGENT_ENABLED=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
    ports:
      - "8126:8126"  # APM trace intake

  # Lightdash (self-hosted, open-source)
  lightdash:
    image: lightdash/lightdash:latest
    ports:
      - "8080:8080"
    environment:
      - LIGHTDASH_SECRET=${LIGHTDASH_SECRET}
    volumes:
      - lightdash-data:/app/data

volumes:
  lightdash-data:
```

---

## Environment Variables

```bash
# .env (DO NOT COMMIT)
GEMINI_API_KEY=your_gemini_api_key
BRAINTRUST_API_KEY=your_braintrust_api_key
AIRIA_API_KEY=your_airia_api_key
MODULATE_API_KEY=your_modulate_api_key
MODULATE_STT_STREAMING_URL=https://modulate-prototype-apis.com/api/velma-2-stt-streaming
MODULATE_STT_BATCH_URL=https://modulate-prototype-apis.com/api/velma-2-stt-batch
MODULATE_STT_BATCH_ENGLISH_VFAST_URL=https://modulate-prototype-apis.com/api/velma-2-stt-batch-english-vfast
FLORA_API_KEY=your_flora_api_key
DD_API_KEY=your_datadog_api_key
LIGHTDASH_SECRET=your_lightdash_secret
```

---

## Service Port Map

| Service | Port | URL |
|---|---|---|
| FastAPI Backend | 8000 | `http://localhost:8000` |
| React Frontend | 3000 | `http://localhost:3000` |
| Datadog APM Intake | 8126 | `http://localhost:8126` |
| Lightdash Dashboard | 8080 | `http://localhost:8080` |

---

## Startup Commands

```bash
# Build and start all services
docker-compose up --build

# Start in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Tear down
docker-compose down -v
```

---

**Prev**: [Frontend Architecture](./06-frontend-architecture.md) | **Next**: [Observability](./08-observability.md) | [Full Index](../ARCHITECTURE.md)
