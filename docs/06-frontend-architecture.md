# Frontend Architecture

## Tech Choice: React + Vite

For a full web dashboard in a 24-hour hackathon, we use **React + Vite** with **Tailwind CSS** and **shadcn/ui** for rapid, beautiful UI development. The frontend communicates with the FastAPI backend via REST.

---

## Pages & Components

```
src/
├── pages/
│   ├── Dashboard.tsx          # Main overview — active signals, recent campaigns
│   ├── Onboarding.tsx         # Company onboarding wizard (Agent 1)
│   ├── TrendSignals.tsx       # Live Polymarket signals feed (Agent 2)
│   ├── Campaigns.tsx          # Campaign list and detail view (Agent 3 + 4)
│   ├── CampaignDetail.tsx     # Single campaign with metrics, visuals, routing
│   ├── Analytics.tsx          # Lightdash-embedded dashboard + custom charts
│   └── Settings.tsx           # Company profile management
├── components/
│   ├── SignalCard.tsx          # Polymarket signal with probability, momentum
│   ├── CampaignCard.tsx       # Campaign preview with headline, confidence, channel
│   ├── LearningCurveChart.tsx # Agent improvement visualization
│   ├── FeedbackLoopDiagram.tsx# Interactive 3-loop diagram
│   ├── SafetyBadge.tsx        # Modulate safety score indicator
│   └── ChannelBadge.tsx       # Distribution channel tag
└── lib/
    ├── api.ts                 # FastAPI client
    └── types.ts               # TypeScript types matching backend models
```

---

## Key UI Moments for Demo

1. **Onboarding Flow**: Clean multi-step form → brand profile appears in real-time
2. **Live Signal Feed**: Polymarket data streaming with probability bars and momentum indicators
3. **Campaign Generation**: Loading animation → 3-5 cards appear with headlines, visual previews (Flora), safety badges (Modulate), and channel tags
4. **Analytics Dashboard**: Embedded Lightdash panels showing learning curves trending upward
5. **Feedback Trigger**: Button to run feedback cycle → watch metrics update in real-time

---

## Page Breakdown

### Dashboard (Home)
- **Top Row**: Active Polymarket signals with sparkline charts
- **Middle**: Recent campaigns with status badges (draft / approved / posted)
- **Bottom**: Key metrics — total campaigns, avg engagement, system health
- **Sidebar**: Quick-action buttons (new company, refresh signals, trigger feedback)

### Onboarding
- Multi-step wizard: Company Info → Brand Voice → Goals → Review
- Real-time preview of the brand profile being built
- Agent 1 processes in background, profile appears on completion

### Trend Signals
- Live feed of Polymarket signals sorted by relevance to active companies
- Each signal card shows: title, probability bar, momentum arrow, volume, category tag
- Click to expand: detailed reasoning from Agent 2 about why this signal matters

### Campaigns
- Filterable grid: by company, status, channel, confidence score
- Each card: headline, confidence badge, channel tag, safety badge, Flora visual thumbnail
- Bulk actions: approve, archive, regenerate

### Analytics
- Learning Curve chart (Recharts line chart): Agent quality score over time
- Polymarket Calibration chart: Predicted vs actual engagement scatter plot
- Channel Performance: Bar chart by channel type
- Lightdash embedded iframe for advanced BI (if self-hosted instance is running)

---

**Prev**: [API Design](./05-api-design.md) | **Next**: [Infrastructure](./07-infrastructure.md) | [Full Index](../ARCHITECTURE.md)
