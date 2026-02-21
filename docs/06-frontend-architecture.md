# Frontend Architecture

## Tech Choice: React + Vite

For a full web dashboard in a 24-hour hackathon, we use **React + Vite** with **Tailwind CSS** and **shadcn/ui** for rapid, beautiful UI development. The frontend communicates with the FastAPI backend via REST.

---

## Pages & Components

```
src/
├── pages/
│   ├── Generate.jsx           # Campaign generation chat UI (Agent 1-4 pipeline)
│   ├── Campaigns.jsx          # Campaign list and management
│   ├── ContentStudio.jsx      # Content strategy + generated content viewer (Agent 6 + 7)
│   ├── Trending.jsx           # Live Polymarket signals feed (Agent 2)
├── components/
│   ├── Layout.jsx             # Main layout with sidebar
│   ├── Sidebar.jsx            # Navigation sidebar
│   ├── CampaignCard.jsx       # Campaign preview with headline, confidence, channel
│   ├── ChannelBadge.jsx       # Distribution channel tag
│   └── ChecklistItem.jsx     # Progress checklist item
└── lib/
    └── utils.js               # Utility functions, mock data, channel config
```

---

## Key UI Moments for Demo

1. **Onboarding Flow**: Clean multi-step form → brand profile appears in real-time
2. **Live Signal Feed**: Polymarket data streaming with probability bars and momentum indicators
3. **Campaign Generation**: Loading animation → 3-5 cards appear with headlines, Gemini-generated visual previews, voice-match badges (Modulate-informed), and channel tags
4. **Content Studio**: Agent 6 strategy cards expand to reveal Agent 7's full content — tweet threads with individual tweet previews, full LinkedIn articles, newsletter copy — all with copy buttons and quality scores
6. **Feedback Trigger**: Button to run feedback cycle → watch metrics update in real-time

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
- Each card: headline, confidence badge, channel tag, voice-match badge, Gemini media thumbnail
- Bulk actions: approve, archive, regenerate

### Analytics
- Learning Curve chart (Recharts line chart): Agent quality score over time
- Polymarket Calibration chart: Predicted vs actual engagement scatter plot
- Channel Performance: Bar chart by channel type

---

**Prev**: [API Design](./05-api-design.md) | **Next**: [Infrastructure](./07-infrastructure.md) | [Full Index](../ARCHITECTURE.md)
