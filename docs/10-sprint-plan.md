# MVP Scope & Sprint Plan

## 24-Hour Sprint Breakdown

### Hour 0–2: Foundation (Infrastructure)
- [ ] Initialize project structure (backend/, frontend/, docker/)
- [ ] Set up FastAPI skeleton with health endpoint
- [ ] Set up React + Vite + Tailwind + shadcn/ui
- [ ] Configure Docker Compose with all services
- [ ] Set up SQLite database with schema
- [ ] Configure Datadog agent + ddtrace
- [ ] Set up environment variables

### Hour 2–6: Core Agents (Agent 1 + Agent 2)
- [ ] Implement Brand Intake Agent with Gemini API via ADK
- [ ] Build onboarding API endpoint + frontend form
- [ ] Implement Polymarket Gamma API polling
- [ ] Build Trend Intelligence Agent with signal scoring
- [ ] Wire Braintrust tracing on both agents
- [ ] Build Signal Feed UI component

### Hour 6–12: Generation Pipeline (Agent 3 + Agent 4)
- [ ] Implement Campaign Generation Agent with brand-aware prompting
- [ ] Integrate Flora AI for visual asset generation
- [ ] Implement Modulate AI safety gate
- [ ] Build Distribution Routing Agent with channel scoring
- [ ] Wire full pipeline: Signal → Campaign → Safety → Route
- [ ] Build Campaign Cards UI with safety badges and channel tags
- [ ] Set up Airia workflow connecting all agents

### Hour 12–16: Feedback Loops (Agent 5)
- [ ] Implement Loop 1: Campaign performance → prompt weight updates
- [ ] Implement Loop 3: Signal-to-engagement calibration
- [ ] Implement Loop 2: Cross-company pattern extraction (simplified)
- [ ] Integrate Braintrust Loop Agent for automated prompt improvement
- [ ] Build simulated performance data generator (for demo)
- [ ] Apply Cleric memory patterns to episodic storage

### Hour 16–20: Analytics & Dashboard
- [ ] Set up Lightdash with campaign metrics data
- [ ] Build Learning Curve chart (agent improvement over time)
- [ ] Build Polymarket Calibration chart
- [ ] Build Datadog dashboard with custom metrics
- [ ] Build main Dashboard page aggregating all views
- [ ] Embed Lightdash panels or replicate key charts in React

### Hour 20–24: Polish & Demo Prep
- [ ] End-to-end demo flow testing
- [ ] Seed compelling demo data (real Polymarket signals)
- [ ] Polish UI transitions and loading states
- [ ] Prepare 7-minute demo script
- [ ] Test all sponsor integrations are visible and working
- [ ] Record backup demo video

---

## MVP vs. Stretch Goals

| Feature | MVP (Must Have) | Stretch |
|---|---|---|
| Company onboarding | Simple form → profile | Conversational AI onboarding |
| Polymarket signals | Poll + display top 5 | Real-time WebSocket stream |
| Campaign generation | 3 campaigns per signal | A/B tested via Airia Battleground |
| Visual assets | Flora generates 1 image | Multiple style variations |
| Safety check | Modulate score + badge | Full appeals workflow |
| Distribution routing | Channel recommendation | Auto-post to Twitter API |
| Feedback Loop 1 | Simulated metrics → weight update | Real engagement tracking |
| Feedback Loop 2 | Demo pattern extraction | True federated learning |
| Feedback Loop 3 | Signal accuracy tracking | Bayesian calibration model |
| Lightdash dashboard | 3-4 key charts | Full BI with dbt metrics |
| Datadog monitoring | APM + custom metrics | Full alerting + SLOs |
| Cleric patterns | Memory architecture | Progressive trust automation |

---

## Priority Order (if running out of time)

1. **Must ship**: Agents 1-3 working end-to-end with Gemini + Braintrust tracing
2. **Must ship**: At least one feedback loop demonstrably updating weights
3. **Must ship**: Datadog APM traces visible in dashboard
4. **High priority**: Frontend showing signal → campaign flow
5. **High priority**: Modulate safety gate with visual badge
6. **Medium**: Lightdash dashboard with learning curve chart
7. **Medium**: Flora AI generated visuals on campaign cards
8. **Nice to have**: Airia orchestration visible in Agent Studio
9. **Nice to have**: Cleric memory patterns implemented
10. **Nice to have**: Full Loop 2 cross-company learning

---

**Prev**: [Security & Safety](./09-security-safety.md) | **Next**: [Tech Stack](./11-tech-stack.md) | [Full Index](../ARCHITECTURE.md)
