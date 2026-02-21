# SIGNAL Frontend Architecture

## Overview

The SIGNAL frontend is a modern React application built with Vite, TypeScript, and Tailwind CSS. It provides a clean, intuitive interface for the self-improving content intelligence platform.

## Technology Stack

### Core
- **React 18.2** - Component-based UI framework
- **TypeScript 5.2** - Static typing and enhanced developer experience
- **Vite 5.1** - Fast build tool and dev server with HMR

### Styling
- **Tailwind CSS 3.4** - Utility-first CSS framework
- **Custom Design System** - Consistent colors, spacing, and components

### Routing & State
- **React Router 6.22** - Client-side routing
- **Local State** - useState/useEffect for component state
- **API Integration** - Axios for HTTP requests

### Data Visualization
- **Recharts 2.12** - Composable charting library for analytics

### Icons & UI
- **Lucide React** - Modern icon library
- **Custom Components** - Reusable UI components

## Architecture Patterns

### Component Structure

```
┌─────────────────────────────────────┐
│           App (Router)              │
└─────────────────┬───────────────────┘
                  │
         ┌────────▼────────┐
         │     Layout      │
         │   (Sidebar)     │
         └────────┬────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐   ┌────▼────┐   ┌───▼────┐
│ Pages │   │Components│   │  Lib   │
│       │   │          │   │        │
│ - Dashboard│ - SignalCard│ - api.ts│
│ - Onboarding│ - CampaignCard│ - types.ts│
│ - Signals│   │          │   │ - utils.ts│
│ - Campaigns│ │          │   │        │
│ - Analytics│ │          │   │        │
│ - Settings│  │          │   │        │
└───────┘   └──────────┘   └────────┘
```

### Data Flow

```
User Action
    │
    ▼
Component Event Handler
    │
    ▼
API Call (lib/api.ts)
    │
    ▼
FastAPI Backend (/api/v1/*)
    │
    ▼
Response Data
    │
    ▼
Update Component State
    │
    ▼
Re-render UI
```

### API Integration Layer

The `lib/api.ts` module provides typed API functions:

```typescript
// Example: Generate campaigns
const response = await generateCampaigns({
  company_id: 'comp_123',
  signal_id: 'sig_456',
  num_concepts: 3
})
// Response is typed as { concepts: Campaign[] }
```

All API calls:
- Use Axios with base URL `/api/v1`
- Return typed responses matching backend models
- Handle errors with try/catch in components
- Show loading states during async operations

## Page Breakdown

### Dashboard (`/`)
**Purpose**: System overview and quick actions

**Features**:
- Active signals count
- Total campaigns count
- System health status
- Recent signals preview (top 3)
- Recent campaigns preview (top 6)
- Trigger feedback loop button

**Data Sources**:
- `GET /signals` - Active trend signals
- `GET /campaigns` - Recent campaigns
- `GET /health` - System status
- `POST /feedback/trigger` - Manual feedback

### Onboarding (`/onboarding`)
**Purpose**: Create new company profiles

**Features**:
- Multi-field form for brand details
- Real-time validation
- Competitor list (comma-separated)
- Safety threshold configuration
- Success/error feedback

**Data Flow**:
- Form submission → `POST /companies`
- Success → Navigate to dashboard
- Error → Show alert

### Trend Signals (`/signals`)
**Purpose**: View live Polymarket data

**Features**:
- Grid of signal cards
- Probability bars with momentum indicators
- Volume and velocity metrics
- Category tags
- Manual refresh button

**Data Sources**:
- `GET /signals` - Current signals
- `POST /signals/refresh` - Fetch new data

**Visual Elements**:
- Green/red momentum badges
- Animated probability bars
- Sparkline-style indicators

### Campaigns (`/campaigns`)
**Purpose**: Manage and generate campaigns

**Features**:
- Campaign grid with filters
- Generate modal (company + signal selection)
- Status badges (draft/approved/posted)
- Channel icons
- Safety scores
- Confidence indicators
- Click to view details

**Data Sources**:
- `GET /campaigns` - All campaigns
- `GET /companies` - For generation modal
- `GET /signals` - For generation modal
- `POST /campaigns/generate` - Create new campaigns

**Generation Flow**:
1. Click "Generate Campaigns"
2. Select company from dropdown
3. Select trend signal from dropdown
4. Submit → Agent 3 + 4 pipeline runs
5. New campaigns appear in grid

### Campaign Detail (`/campaigns/:id`)
**Purpose**: Full campaign view and approval

**Features**:
- Full headline and body copy
- Visual asset preview (if available)
- Visual direction notes
- Channel recommendation with reasoning
- Safety score badge
- Confidence score
- Approve button (for draft status)
- Back navigation

**Data Sources**:
- `GET /campaigns/:id` - Campaign details
- `POST /campaigns/:id/approve` - Approve campaign

### Analytics (`/analytics`)
**Purpose**: Visualize system learning and performance

**Features**:
- Learning curve line chart (quality over time)
- Signal calibration bar chart (predicted vs actual)
- Three loops diagram (interactive cards)
- Empty states with helpful messages

**Data Sources**:
- `GET /analytics/learning-curve`
- `GET /analytics/calibration`

**Charts**:
- Recharts library for responsive visualizations
- Line chart for trends over time
- Bar chart for comparisons
- Custom tooltips and legends

### Settings (`/settings`)
**Purpose**: Manage company profiles and system config

**Features**:
- List of all company profiles
- Company details display
- Creation timestamps
- System information panel

**Data Sources**:
- `GET /companies` - All profiles

## Component Library

### Layout
**File**: `components/Layout.tsx`

**Purpose**: Main application shell with sidebar navigation

**Features**:
- Fixed sidebar with logo
- Navigation menu with active state
- Quick action button (New Company)
- Responsive content area

### SignalCard
**File**: `components/SignalCard.tsx`

**Purpose**: Display Polymarket trend signal

**Props**:
- `signal: TrendSignal` - Signal data
- `onClick?: () => void` - Click handler

**Features**:
- Title and category badge
- Momentum indicator (up/down arrow)
- Probability bar with percentage
- Volume and velocity stats
- Hover effect

### CampaignCard
**File**: `components/CampaignCard.tsx`

**Purpose**: Campaign preview in grid

**Props**:
- `campaign: Campaign` - Campaign data
- `onClick?: () => void` - Click handler

**Features**:
- Headline and body preview (truncated)
- Visual asset thumbnail
- Status badge (colored by status)
- Channel icon and name
- Confidence score
- Safety badge (pass/fail)
- Creation timestamp
- Hover effect

## Type System

### Core Types (`lib/types.ts`)

```typescript
interface CompanyProfile {
  id: string
  name: string
  industry: string
  tone_of_voice?: string
  target_audience?: string
  campaign_goals?: string
  competitors: string[]
  content_history: string[]
  visual_style?: string
  safety_threshold: number
  created_at: string
  updated_at: string
}

interface TrendSignal {
  id: string
  polymarket_market_id: string
  title: string
  category?: string
  probability: number
  probability_momentum: number
  volume: number
  volume_velocity: number
  relevance_scores: Record<string, number>
  confidence_score: number
  surfaced_at: string
  expires_at?: string
}

interface Campaign {
  id: string
  company_id?: string
  trend_signal_id?: string
  headline: string
  body_copy: string
  visual_direction: string
  visual_asset_url?: string
  confidence_score: number
  channel_recommendation: 'twitter' | 'linkedin' | 'instagram' | 'newsletter'
  channel_reasoning: string
  safety_score?: number
  safety_passed: boolean
  status: 'draft' | 'approved' | 'posted' | 'completed'
  created_at: string
}
```

## Styling System

### Tailwind Configuration

**Colors**:
- Primary: Blue (`#3b82f6`)
- Success: Green (`#10b981`)
- Warning: Yellow (`#f59e0b`)
- Danger: Red (`#ef4444`)
- Gray scale: 50-900

**Spacing**: 4px base unit (0.25rem)

**Border Radius**: 
- sm: 0.125rem
- md: 0.375rem
- lg: 0.5rem

**Shadows**: Subtle elevation for cards and modals

### Component Patterns

**Card**:
```tsx
<div className="bg-white rounded-lg border border-gray-200 p-6">
  {/* content */}
</div>
```

**Button Primary**:
```tsx
<button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90">
  {/* label */}
</button>
```

**Badge**:
```tsx
<span className="px-2 py-1 text-xs font-medium bg-primary/10 text-primary rounded">
  {/* text */}
</span>
```

## State Management

### Local State Pattern

Each page manages its own state with `useState`:

```typescript
const [data, setData] = useState<Type[]>([])
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)

useEffect(() => {
  loadData()
}, [])

const loadData = async () => {
  try {
    const res = await apiCall()
    setData(res.data)
  } catch (err) {
    setError(err.message)
  } finally {
    setLoading(false)
  }
}
```

### No Global State

The app uses local component state only. For a hackathon MVP, this is sufficient. Future enhancements could add:
- React Context for shared state
- React Query for server state caching
- Zustand for global client state

## Performance Considerations

### Code Splitting
- React Router handles route-based code splitting
- Each page is a separate chunk
- Lazy loading not needed for MVP size

### API Optimization
- No caching layer (direct API calls)
- Loading states prevent duplicate requests
- Manual refresh for data updates

### Rendering
- Minimal re-renders (local state scoped to pages)
- No expensive computations
- Recharts handles chart optimization

## Development Workflow

### Local Development
1. Start backend: `cd code/backend && uvicorn main:app --reload`
2. Start frontend: `cd code/frontend && npm run dev`
3. Open `http://localhost:3000`
4. Changes hot-reload automatically

### Building
1. `npm run build` - TypeScript compile + Vite build
2. Output in `dist/` directory
3. `npm run preview` - Test production build locally

### Linting
- ESLint configured for React + TypeScript
- `npm run lint` - Check for issues
- Auto-fix on save (if editor configured)

## Future Enhancements

### Short Term
- Real-time updates (WebSocket for live signals)
- Campaign editing and regeneration
- Bulk campaign actions
- Advanced filtering and search
- Export campaigns to CSV/PDF

### Medium Term
- User authentication and roles
- Multi-workspace support
- Campaign scheduling
- A/B testing interface
- Performance metrics dashboard

### Long Term
- Mobile app (React Native)
- Collaborative features (comments, approvals)
- Custom agent configuration UI
- Prompt template editor
- Integration marketplace

## Demo Tips

### For Hackathon Judges

1. **Start Clean**: Clear browser cache, fresh data
2. **Pre-seed Data**: Have 1-2 companies and signals ready
3. **Practice Flow**: Rehearse the 7-minute demo
4. **Show Loading**: Let them see the AI working
5. **Highlight Loops**: Emphasize the self-improving aspect
6. **Visual Impact**: Use the Analytics page for "wow" moment

### Key Talking Points

- "Real-time Polymarket integration"
- "Multi-agent pipeline visualization"
- "Self-improving feedback loops"
- "Enterprise-ready architecture"
- "Type-safe, modern stack"

### Common Questions

**Q: How does it improve over time?**
A: Show the Analytics page, explain the three loops, point to learning curve chart.

**Q: What makes this different from other tools?**
A: Prediction markets as leading indicators, not lagging social media trends.

**Q: Can it handle multiple companies?**
A: Yes, show Settings page with multiple profiles, explain cross-company learning.

**Q: Is it production-ready?**
A: MVP for hackathon, but architecture is scalable (TypeScript, modular design, API-first).
